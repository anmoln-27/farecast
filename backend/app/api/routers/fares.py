"""
backend/app/api/routers/fares.py
---------------------------------
GET /api/fares — query historical fare observations.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.db.models import FareObservation
from backend.app.schemas.responses import FaresResponse, FareRecord, PaginationMeta

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Fares"])


@router.get("/fares", response_model=FaresResponse, summary="Historical fare observations")
def list_fares(
    origin: Optional[str] = Query(None, description="IATA origin code, e.g. DEL"),
    destination: Optional[str] = Query(None, description="IATA destination code, e.g. BOM"),
    airline: Optional[str] = Query(None, description="Airline code, e.g. 6E"),
    cabin_class: Optional[str] = Query(None, description="Economy / Business"),
    advance_window: Optional[str] = Query(None, description="Advance window: T+1, T+7, T+15, T+30, T+45"),
    data_mode: Optional[str] = Query(None, description="Data mode: LIVE, HISTORICAL, DEMO"),
    travel_date_from: Optional[date] = Query(None),
    travel_date_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> FaresResponse:
    """
    Query historical and live airfare observations stored in the database.
    Supports filtering by route, airline, cabin class, advance window, data mode, and date range.
    """
    try:
        q = db.query(FareObservation)

        if origin:
            q = q.filter(FareObservation.origin == origin.upper())
        if destination:
            q = q.filter(FareObservation.destination == destination.upper())
        if airline:
            q = q.filter(FareObservation.airline_code == airline.upper())
        if cabin_class:
            q = q.filter(cast(FareObservation.cabin_class, String).ilike(f"%{cabin_class}%"))
        if advance_window:
            q = q.filter(FareObservation.advance_window == advance_window.upper())
        if data_mode:
            q = q.filter(cast(FareObservation.data_mode, String) == data_mode.upper())
        if travel_date_from:
            q = q.filter(FareObservation.travel_date >= travel_date_from)
        if travel_date_to:
            q = q.filter(FareObservation.travel_date <= travel_date_to)

        total = q.count()
        records = q.order_by(FareObservation.travel_date.desc()).offset(offset).limit(limit).all()

        return FaresResponse(
            data=[FareRecord.model_validate(r) for r in records],
            meta=PaginationMeta(total=total, limit=limit, offset=offset),
        )
    except Exception as exc:
        logger.error("Failed to query fares: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {exc}",
        )


CITY_NAMES = {
    "DEL": "Delhi",
    "BOM": "Mumbai",
    "BLR": "Bengaluru",
    "CCU": "Kolkata",
    "HYD": "Hyderabad",
    "MAA": "Chennai",
    "GOI": "Goa",
    "PNQ": "Pune",
    "AMD": "Ahmedabad",
}

WINDOW_DAYS = {
    "T+45": 45,
    "T+30": 30,
    "T+15": 15,
    "T+7": 7,
    "T+1": 1,
}


@router.get("/fares/elasticity", summary="Real lead-time elasticity by advance-purchase window")
def get_lead_time_elasticity(
    origin: Optional[str] = Query(None, description="Origin code, e.g. DEL"),
    destination: Optional[str] = Query(None, description="Destination code, e.g. BOM"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Returns empirical average airfare across advance-purchase windows (T+45 -> T+1)
    computed directly from real observed database flights.
    """
    from sqlalchemy import func
    from backend.app.services.schema import compute_fare_disaggregation

    q = (
        db.query(
            FareObservation.origin,
            FareObservation.destination,
            FareObservation.advance_window,
            func.avg(FareObservation.fare).label("avg_fare"),
            func.count(FareObservation.id).label("count"),
        )
        .filter(FareObservation.advance_window.isnot(None))
    )

    if origin and destination:
        q = q.filter(
            FareObservation.origin == origin.upper(),
            FareObservation.destination == destination.upper(),
        )

    results = q.group_by(
        FareObservation.origin,
        FareObservation.destination,
        FareObservation.advance_window,
    ).all()

    # Organize by route
    routes_data: dict[str, list[dict]] = {}
    ordered_windows = ["T+45", "T+30", "T+15", "T+7", "T+1"]

    raw_by_route_win: dict[str, dict[str, tuple[float, int]]] = {}
    for r_orig, r_dest, win, avg_f, cnt in results:
        route_key = f"{r_orig}-{r_dest}"
        if route_key not in raw_by_route_win:
            raw_by_route_win[route_key] = {}
        raw_by_route_win[route_key][win] = (float(avg_f), int(cnt))

    for route_key, win_dict in raw_by_route_win.items():
        orig_code = route_key.split("-")[0]
        # Base anchor for surge multiplier is T+45 (or oldest available)
        anchor_fare = None
        for w in ordered_windows:
            if w in win_dict:
                anchor_fare = win_dict[w][0]
                break

        pts = []
        for w in ordered_windows:
            if w in win_dict:
                avg_f, cnt = win_dict[w]
                surge_val = round(avg_f / anchor_fare, 2) if anchor_fare and anchor_fare > 0 else 1.0
                disagg = compute_fare_disaggregation(avg_f, origin=orig_code, airline_code="6E")
                pts.append({
                    "window": w,
                    "days": WINDOW_DAYS.get(w, 15),
                    "total": round(avg_f, 2),
                    "base": disagg["base_fare"],
                    "taxes": disagg["taxes"],
                    "udf": disagg["udf_charge"],
                    "fee": disagg["convenience_fee"],
                    "surge": f"{surge_val:.2f}x",
                    "observation_count": cnt,
                })
        if pts:
            routes_data[route_key] = pts

    return {
        "status": "success",
        "data": routes_data,
        "available_routes": list(routes_data.keys()),
        "disclaimer": (
            "Total fares are empirical averages from observed flight observations. "
            "Base fare, tax, UDF, and convenience fees are computed via Reference Tariff Decomposition — Estimated."
        ),
    }


@router.get("/fares/sector-matrix", summary="Real sector surge pricing heatmap matrix")
def get_sector_matrix(db: Session = Depends(get_db)) -> dict:
    """
    Returns real empirical average fares matrix across Indian domestic sectors and
    advance-purchase windows (T+45, T+30, T+15, T+7, T+1) directly from database observations.
    """
    from sqlalchemy import func
    from backend.app.analytics.index_engine import PROTOTYPE_ROUTE_TRAFFIC_WEIGHTS, compute_dgca_route_weights

    route_weights, weight_provenance = compute_dgca_route_weights(db)

    results = (
        db.query(
            FareObservation.origin,
            FareObservation.destination,
            FareObservation.advance_window,
            func.avg(FareObservation.fare).label("avg_fare"),
            func.count(FareObservation.id).label("count"),
        )
        .filter(FareObservation.advance_window.isnot(None))
        .group_by(
            FareObservation.origin,
            FareObservation.destination,
            FareObservation.advance_window,
        )
        .all()
    )

    sectors: dict[str, dict] = {}
    for r_orig, r_dest, win, avg_f, cnt in results:
        route_key = f"{r_orig}-{r_dest}"
        if route_key not in sectors:
            w_val = route_weights.get(route_key, 0.035)
            sectors[route_key] = {
                "route": route_key,
                "originCity": CITY_NAMES.get(r_orig, r_orig),
                "destCity": CITY_NAMES.get(r_dest, r_dest),
                "dgcaWeight": f"{(w_val * 100):.1f}%",
                "weight_value": w_val,
                "fares": {},
                "total_observations": 0,
            }
        sectors[route_key]["fares"][win] = round(float(avg_f), 2)
        sectors[route_key]["total_observations"] += int(cnt)

    # Sort sectors by traffic weight / observation volume descending
    sorted_sectors = sorted(
        sectors.values(),
        key=lambda s: s.get("weight_value", 0.0),
        reverse=True,
    )

    return {
        "status": "success",
        "data_mode": "HISTORICAL",
        "sectors": sorted_sectors,
        "data": sorted_sectors,
        "total_sectors": len(sorted_sectors),
        "weight_source": weight_provenance,
        "provenance_note": (
            f"Weights derived from {weight_provenance}. "
            "Cell values represent empirical average fares (INR) across advance purchase windows."
        ),
    }
