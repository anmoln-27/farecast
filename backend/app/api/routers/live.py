"""
backend/app/api/routers/live.py
---------------------------------
GET /api/live/search  — live airfare search via Amadeus (or DEMO fallback)
GET /api/live/status  — Amadeus connectivity and configuration status

SECURITY:
  - Never returns AMADEUS_CLIENT_ID or AMADEUS_CLIENT_SECRET
  - DEMO_MODE=true bypasses all live API calls
  - Credentials missing → DEMO mode automatically
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_settings
from backend.app.core.config import Settings
from backend.app.db.models import FareObservation
from backend.app.schemas.responses import (
    LiveFareOffer,
    LiveSearchResponse,
    LiveStatusResponse,
)
from backend.app.services.amadeus_service import (
    AmadeusAuthError,
    AmadeusSearchError,
    AmadeusService,
    get_amadeus_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/live", tags=["Live"])

_AMADEUS_DISCLAIMER = (
    "Amadeus Flight Offers Search results. "
    "Coverage does NOT include every Indian domestic airline or route. "
    "Fares are in EUR (INR estimate is approximate). "
    "This is NOT a booking system."
)

_DEMO_DISCLAIMER = (
    "DEMO mode: returning HISTORICAL data from the local database. "
    "No live Amadeus API call was made."
)


# ─── /api/live/status ─────────────────────────────────────────────────────────

@router.get("/status", response_model=LiveStatusResponse, summary="Amadeus live status")
def live_status(settings: Settings = Depends(get_settings)) -> LiveStatusResponse:
    """
    Return configuration and connectivity status for the live Amadeus integration.
    NEVER returns credentials.
    """
    amadeus_configured = bool(
        settings.AMADEUS_CLIENT_ID and settings.AMADEUS_CLIENT_SECRET
    )

    if settings.DEMO_MODE:
        return LiveStatusResponse(
            demo_mode=True,
            amadeus_configured=amadeus_configured,
            amadeus_reachable=None,
            mode_label="DEMO",
            message=(
                "Application is running in DEMO mode. "
                "Set DEMO_MODE=false and supply Amadeus credentials to enable live search."
            ),
        )

    if not amadeus_configured:
        return LiveStatusResponse(
            demo_mode=False,
            amadeus_configured=False,
            amadeus_reachable=None,
            mode_label="DEMO (missing credentials)",
            message=(
                "Amadeus credentials are not configured. "
                "Set AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET environment variables."
            ),
        )

    # Check connectivity without exposing credentials in response
    svc = get_amadeus_service(settings)
    reachable = svc.check_connectivity()

    return LiveStatusResponse(
        demo_mode=False,
        amadeus_configured=True,
        amadeus_reachable=reachable,
        mode_label="LIVE" if reachable else "LIVE (unreachable)",
        message=(
            "Amadeus configured and reachable. Live search is active."
            if reachable
            else "Amadeus configured but connectivity check failed. "
                 "Check network or API status."
        ),
    )


# ─── /api/live/search ─────────────────────────────────────────────────────────

@router.get("/search", response_model=LiveSearchResponse, summary="Live airfare search")
def live_search(
    origin: str = Query(..., description="IATA origin code, e.g. DEL"),
    destination: str = Query(..., description="IATA destination code, e.g. BOM"),
    departure_date: str = Query(..., description="ISO date, e.g. 2024-12-01"),
    adults: int = Query(default=1, ge=1, le=9),
    travel_class: str = Query(default="ECONOMY", description="ECONOMY / BUSINESS / FIRST"),
    max_results: int = Query(default=10, ge=1, le=50),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> LiveSearchResponse:
    """
    Search for live airfares via Amadeus Flight Offers Search.

    - When DEMO_MODE=true or credentials are missing: returns clearly labelled
      HISTORICAL data from the local database.
    - When live: returns Amadeus results labelled LIVE.
    - NEVER fabricates live data.
    - NEVER exposes API credentials.

    Coverage note: Amadeus does not cover every Indian domestic airline.
    """
    # Validate departure_date format
    try:
        date.fromisoformat(departure_date)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="departure_date must be ISO format: YYYY-MM-DD",
        )

    # DEMO / fallback path
    if not settings.amadeus_available:
        return _demo_fallback(origin, destination, db, settings)

    # Live path
    svc = get_amadeus_service(settings)
    try:
        raw_offers = svc.search_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            adults=adults,
            travel_class=travel_class,
            max_results=max_results,
        )
    except AmadeusAuthError as exc:
        logger.error("Amadeus auth error during search: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="Amadeus authentication failed. Check credentials configuration.",
        )
    except AmadeusSearchError as exc:
        logger.error("Amadeus search error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="Amadeus flight search failed. Try again or switch to DEMO mode.",
        )

    offers = [LiveFareOffer(**o) for o in raw_offers]

    return LiveSearchResponse(
        data_mode="LIVE",
        source="AMADEUS",
        disclaimer=_AMADEUS_DISCLAIMER,
        offers=offers,
        total=len(offers),
    )


# ─── Demo fallback ────────────────────────────────────────────────────────────

def _demo_fallback(
    origin: str,
    destination: str,
    db: Session,
    settings: Settings,
) -> LiveSearchResponse:
    """
    Return clearly-labelled HISTORICAL/DEMO data from the local DB.
    Never pretends to be live data.
    """
    records = (
        db.query(FareObservation)
        .filter(
            FareObservation.origin == origin.upper(),
            FareObservation.destination == destination.upper(),
        )
        .order_by(FareObservation.travel_date.desc())
        .limit(10)
        .all()
    )

    mode = "DEMO" if settings.DEMO_MODE else "HISTORICAL"
    offers = [
        LiveFareOffer(
            source="HISTORICAL",
            data_mode=mode,
            origin=r.origin,
            destination=r.destination,
            airline_code=r.airline_code,
            airline_name=None,
            departure_datetime=str(r.travel_date) if r.travel_date else None,
            arrival_datetime=None,
            duration_minutes=r.duration_minutes,
            stops=r.stops or 0,
            cabin_class=r.cabin_class.value if hasattr(r.cabin_class, "value") else str(r.cabin_class or "Economy"),
            fare=r.fare,
            currency=r.currency or "INR",
            fare_inr_estimate=r.fare if (r.currency or "INR") == "INR" else None,
            collected_at=r.collected_at or datetime.now(timezone.utc),
        )
        for r in records
    ]

    return LiveSearchResponse(
        data_mode=mode,
        source="HISTORICAL",
        disclaimer=_DEMO_DISCLAIMER,
        offers=offers,
        total=len(offers),
    )
