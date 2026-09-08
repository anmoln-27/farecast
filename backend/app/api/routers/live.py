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
from backend.app.services.ignav_service import (
    IgnavAuthError,
    IgnavConfigError,
    IgnavSearchError,
    IgnavService,
    get_ignav_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/live", tags=["Live"])

_AMADEUS_DISCLAIMER = (
    "Amadeus Flight Offers Search results. "
    "Coverage does NOT include every Indian domestic airline or route. "
    "Fares are in EUR (INR estimate is approximate). "
    "This is NOT a booking system."
)

_IGNAV_DISCLAIMER = (
    "Ignav Live Airfare API results. "
    "Real-time one-way flight search with Indian domestic market coverage. "
    "This is NOT a booking system."
)

_DEMO_DISCLAIMER = (
    "DEMO mode: returning HISTORICAL data from the local database. "
    "No live API call was made."
)


# ─── /api/live/status ─────────────────────────────────────────────────────────

@router.get("/status", response_model=LiveStatusResponse, summary="Live status")
def live_status(settings: Settings = Depends(get_settings)) -> LiveStatusResponse:
    """
    Return configuration and connectivity status for live integrations (Ignav / Amadeus).
    NEVER returns credentials or secrets.
    """
    ignav_configured = bool(settings.ignav_available)
    amadeus_configured = bool(
        settings.AMADEUS_CLIENT_ID and settings.AMADEUS_CLIENT_SECRET
    )

    # 1. Ignav configured (Primary live provider)
    if ignav_configured:
        return LiveStatusResponse(
            demo_mode=settings.DEMO_MODE,
            amadeus_configured=amadeus_configured,
            ignav_configured=True,
            active_provider="IGNAV",
            amadeus_reachable=None,
            mode_label="LIVE (Ignav)",
            message="Ignav live airfare provider configured and active.",
        )

    # 2. Amadeus configured and DEMO_MODE off (Secondary / enterprise provider)
    if settings.amadeus_available:
        svc = get_amadeus_service(settings)
        reachable = svc.check_connectivity()
        return LiveStatusResponse(
            demo_mode=False,
            amadeus_configured=True,
            ignav_configured=False,
            active_provider="AMADEUS",
            amadeus_reachable=reachable,
            mode_label="LIVE (Amadeus)" if reachable else "LIVE (Amadeus unreachable)",
            message=(
                "Amadeus configured and reachable. Live search is active."
                if reachable
                else "Amadeus configured but connectivity check failed."
            ),
        )

    # 3. DEMO fallback
    mode_label = "DEMO" if settings.DEMO_MODE else "DEMO (missing credentials)"
    return LiveStatusResponse(
        demo_mode=settings.DEMO_MODE,
        amadeus_configured=amadeus_configured,
        ignav_configured=False,
        active_provider="DEMO",
        amadeus_reachable=None,
        mode_label=mode_label,
        message=(
            "Application is running in DEMO mode. "
            "Supply IGNAV_API_KEY to enable real live airfare search."
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
    persist: bool = Query(default=True, description="Persist live search results to fare_observations"),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> LiveSearchResponse:
    """
    Search for live airfares via Ignav (primary) or Amadeus (secondary).

    Provider Selection Hierarchy:
    1. If IGNAV_API_KEY is configured -> Query Ignav Live API (market=IN).
       If Ignav error/unavailable -> safe DEMO fallback (clearly labelled DEMO/HISTORICAL).
    2. Else if Amadeus is configured and DEMO_MODE is false -> Query Amadeus Live.
    3. Else -> safe DEMO fallback.

    - NEVER fabricates live data.
    - NEVER exposes API credentials in logs or responses.
    - NEVER labels fallback/synthetic data as LIVE.
    """
    # Validate departure_date format
    try:
        date.fromisoformat(departure_date)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="departure_date must be ISO format: YYYY-MM-DD",
        )

    # ── 1. Ignav Provider (Primary) ───────────────────────────────────────────
    if settings.ignav_available:
        svc = get_ignav_service(settings)
        try:
            raw_offers = svc.search_flights(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                adults=adults,
                travel_class=travel_class,
                max_results=max_results,
                market="IN",
            )
            offers = [LiveFareOffer(**o) for o in raw_offers]
            persisted_count = 0
            if persist and offers:
                persisted_count = _persist_live_offers(db, offers, departure_date, source="ignav")

            return LiveSearchResponse(
                data_mode="LIVE",
                source="IGNAV",
                disclaimer=_IGNAV_DISCLAIMER,
                offers=offers,
                total=len(offers),
                persisted_count=persisted_count,
            )
        except Exception as exc:
            # Fall back to DEMO mode if Ignav request fails, without claiming to be LIVE
            logger.error("Ignav live search failed (%s), safely falling back to DEMO: %s", type(exc).__name__, exc)
            return _demo_fallback(
                origin,
                destination,
                db,
                settings,
                error_detail=f"Live search via Ignav encountered an issue: {exc}. Displaying verified historical observations fallback.",
            )

    # ── 2. Amadeus Provider (Alternative/Future) ──────────────────────────────
    if settings.amadeus_available:
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
        persisted_count = 0
        if persist and offers:
            persisted_count = _persist_live_offers(db, offers, departure_date, source="amadeus")

        return LiveSearchResponse(
            data_mode="LIVE",
            source="AMADEUS",
            disclaimer=_AMADEUS_DISCLAIMER,
            offers=offers,
            total=len(offers),
            persisted_count=persisted_count,
        )

    # ── 3. DEMO / Fallback Path ───────────────────────────────────────────────
    return _demo_fallback(origin, destination, db, settings)


def _persist_live_offers(
    db: Session,
    offers: list[LiveFareOffer],
    departure_date_str: str,
    source: str = "amadeus",
) -> int:
    """
    Persist verified live offers to fare_observations table under DataMode.LIVE.
    Ensures airline existence and maps advance purchase windows.
    """
    from backend.app.db.models import Airline, CabinClass, DataMode

    try:
        travel_dt = date.fromisoformat(departure_date_str)
    except Exception:
        return 0

    today = date.today()
    days_left = max(0, (travel_dt - today).days)
    if days_left <= 1:
        adv_win = "T+1"
    elif days_left <= 7:
        adv_win = "T+7"
    elif days_left <= 15:
        adv_win = "T+15"
    elif days_left <= 30:
        adv_win = "T+30"
    else:
        adv_win = "T+45"

    cabin_map = {
        "economy": CabinClass.ECONOMY,
        "premium economy": CabinClass.PREMIUM_ECONOMY,
        "business": CabinClass.BUSINESS,
        "first": CabinClass.FIRST,
    }

    persisted = 0
    for o in offers:
        try:
            # Ensure airline code exists
            code = (o.airline_code or "6E").upper()
            existing_airline = db.query(Airline).filter_by(code=code).first()
            if not existing_airline:
                airline_label = o.airline_name or code
                db.add(Airline(code=code, name=airline_label, country="India"))
                db.flush()

            cabin_enum = cabin_map.get(o.cabin_class.lower(), CabinClass.ECONOMY)
            fare_val = float(o.fare_inr_estimate if o.fare_inr_estimate is not None else o.fare)
            curr = "INR" if o.fare_inr_estimate is not None else (o.currency or "INR")

            dep_time = None
            if o.departure_datetime and len(o.departure_datetime) >= 16:
                dep_time = o.departure_datetime[11:16]

            arr_time = None
            if o.arrival_datetime and len(o.arrival_datetime) >= 16:
                arr_time = o.arrival_datetime[11:16]

            obs = FareObservation(
                source=source.lower(),
                data_mode=DataMode.LIVE,
                airline_code=code,
                flight_number=o.flight_number,
                origin=o.origin.upper(),
                destination=o.destination.upper(),
                travel_date=travel_dt,
                booking_date=today,
                departure_time=dep_time,
                arrival_time=arr_time,
                stops=o.stops or 0,
                duration_minutes=o.duration_minutes,
                cabin_class=cabin_enum,
                fare=fare_val,
                currency=curr,
                base_fare=None,
                taxes=None,
                udf_charge=None,
                convenience_fee=None,
                total_fare=fare_val,
                advance_window=adv_win,
                days_left=days_left,
                status="AVAILABLE",
                collected_at=o.collected_at or datetime.now(timezone.utc),
            )
            db.add(obs)
            persisted += 1
        except Exception as exc:
            logger.warning("Failed to persist live fare offer: %s", exc)

    if persisted > 0:
        try:
            db.commit()
            logger.info("Persisted %d LIVE airfare observations from %s.", persisted, source)
        except Exception as exc:
            db.rollback()
            logger.error("DB rollback on persisting live offers: %s", exc)
            return 0

    return persisted


# ─── Demo fallback ────────────────────────────────────────────────────────────

def _demo_fallback(
    origin: str,
    destination: str,
    db: Session,
    settings: Settings,
    error_detail: Optional[str] = None,
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
        disclaimer=error_detail or _DEMO_DISCLAIMER,
        offers=offers,
        total=len(offers),
        error_detail=error_detail,
    )
