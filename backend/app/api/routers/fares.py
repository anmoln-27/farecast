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
from sqlalchemy import String, cast, func
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.db.models import FareObservation
from backend.app.schemas.responses import (
    FaresResponse, FareRecord, PaginationMeta,
    FareAnalyticsResponse, FareSummaryStats, FareTrendPoint,
    AirlineComparisonItem, RouteComparisonItem,
)

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
            q = q.filter(func.upper(FareObservation.origin) == origin.upper())
        if destination:
            q = q.filter(func.upper(FareObservation.destination) == destination.upper())
        if airline:
            q = q.filter(func.upper(FareObservation.airline_code) == airline.upper())
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

        # Compute exact aggregates across the full filtered query
        agg = q.with_entities(
            func.count(FareObservation.id),
            func.avg(FareObservation.fare),
            func.min(FareObservation.fare),
            func.max(FareObservation.fare),
        ).first()

        total = int(agg[0]) if agg and agg[0] else 0
        avg_fare = round(float(agg[1]), 2) if agg and agg[1] is not None else None
        min_fare = round(float(agg[2]), 2) if agg and agg[2] is not None else None
        max_fare = round(float(agg[3]), 2) if agg and agg[3] is not None else None
        is_fallback = False
        fallback_message = None

        if total == 0:
            # Fallback for list_fares: relax date restrictions if set
            if travel_date_from or travel_date_to:
                q_relaxed = db.query(FareObservation)
                if origin:
                    q_relaxed = q_relaxed.filter(func.upper(FareObservation.origin) == origin.upper())
                if destination:
                    q_relaxed = q_relaxed.filter(func.upper(FareObservation.destination) == destination.upper())
                if airline:
                    q_relaxed = q_relaxed.filter(func.upper(FareObservation.airline_code) == airline.upper())
                if cabin_class:
                    q_relaxed = q_relaxed.filter(cast(FareObservation.cabin_class, String).ilike(f"%{cabin_class}%"))
                
                agg_r = q_relaxed.with_entities(
                    func.count(FareObservation.id),
                    func.avg(FareObservation.fare),
                    func.min(FareObservation.fare),
                    func.max(FareObservation.fare),
                ).first()
                if agg_r and agg_r[0]:
                    q = q_relaxed
                    total = int(agg_r[0])
                    avg_fare = round(float(agg_r[1]), 2) if agg_r[1] is not None else None
                    min_fare = round(float(agg_r[2]), 2) if agg_r[2] is not None else None
                    max_fare = round(float(agg_r[3]), 2) if agg_r[3] is not None else None
                    is_fallback = True
                    fallback_message = "Using available observations — no records for the exact selected date."

        records = q.order_by(FareObservation.travel_date.desc()).offset(offset).limit(limit).all()

        return FaresResponse(
            data=[FareRecord.model_validate(r) for r in records],
            meta=PaginationMeta(
                total=total,
                limit=limit,
                offset=offset,
                avg_fare=avg_fare,
                min_fare=min_fare,
                max_fare=max_fare,
                is_fallback=is_fallback,
                fallback_message=fallback_message,
            ),
        )
    except Exception as exc:
        logger.error("Failed to query fares: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {exc}",
        )


@router.get("/fares/analytics", response_model=FareAnalyticsResponse, summary="Filtered fare analytics and time-series")
def get_fares_analytics(
    origin: Optional[str] = Query(None, description="IATA origin code, e.g. DEL"),
    destination: Optional[str] = Query(None, description="IATA destination code, e.g. BOM"),
    airline: Optional[str] = Query(None, description="Airline code, e.g. 6E"),
    cabin_class: Optional[str] = Query(None, description="Economy / Business"),
    advance_window: Optional[str] = Query(None, description="Advance window: T+1, T+7, T+15, T+30, T+45"),
    data_mode: Optional[str] = Query(None, description="Data mode: LIVE, HISTORICAL, DEMO"),
    travel_date_from: Optional[date] = Query(None),
    travel_date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
) -> FareAnalyticsResponse:
    """
    Returns dynamically computed statistical aggregates and complete time-series curves
    for the exact filtered subset of observations across the entire database.
    If the exact filter combination produces zero observations, progressively relaxes
    filters (date -> airline -> cabin -> full dataset) to provide faithful historical context.
    """
    try:
        def build_q(orig, dest, airl, cabin, adv, mode, date_from, date_to):
            query = db.query(FareObservation)
            if orig:
                query = query.filter(func.upper(FareObservation.origin) == orig.upper())
            if dest:
                query = query.filter(func.upper(FareObservation.destination) == dest.upper())
            if airl:
                query = query.filter(func.upper(FareObservation.airline_code) == airl.upper())
            if cabin:
                query = query.filter(cast(FareObservation.cabin_class, String).ilike(f"%{cabin}%"))
            if adv:
                query = query.filter(FareObservation.advance_window == adv.upper())
            if mode:
                query = query.filter(cast(FareObservation.data_mode, String) == mode.upper())
            if date_from:
                query = query.filter(FareObservation.travel_date >= date_from)
            if date_to:
                query = query.filter(FareObservation.travel_date <= date_to)
            return query

        def get_agg(query):
            res = query.with_entities(
                func.count(FareObservation.id),
                func.avg(FareObservation.fare),
                func.min(FareObservation.fare),
                func.max(FareObservation.fare),
            ).first()
            cnt = int(res[0]) if res and res[0] else 0
            avg_val = round(float(res[1]), 2) if res and res[1] is not None else None
            min_val = round(float(res[2]), 2) if res and res[2] is not None else None
            max_val = round(float(res[3]), 2) if res and res[3] is not None else None
            return cnt, avg_val, min_val, max_val

        # Step A: Try user's exact filters
        q = build_q(origin, destination, airline, cabin_class, advance_window, data_mode, travel_date_from, travel_date_to)
        total_obs, avg_f, min_f, max_f = get_agg(q)

        is_fallback = False
        fallback_level = "exact"
        fallback_message = None
        exact_match_found = True

        # Progressive relaxation if 0 observations
        if total_obs == 0:
            exact_match_found = False

            # Step B: Relax date restrictions only
            if travel_date_from or travel_date_to:
                q_b = build_q(origin, destination, airline, cabin_class, advance_window, data_mode, None, None)
                cnt_b, avg_b, min_b, max_b = get_agg(q_b)
                if cnt_b > 0:
                    q = q_b
                    total_obs, avg_f, min_f, max_f = cnt_b, avg_b, min_b, max_b
                    is_fallback = True
                    fallback_level = "relaxed_date"
                    fallback_message = "Using available observations — no records for the exact selected date."

            # Step C: Relax airline if still 0
            if total_obs == 0 and airline:
                q_c = build_q(origin, destination, None, cabin_class, advance_window, data_mode, None, None)
                cnt_c, avg_c, min_c, max_c = get_agg(q_c)
                if cnt_c > 0:
                    q = q_c
                    total_obs, avg_f, min_f, max_f = cnt_c, avg_c, min_c, max_c
                    is_fallback = True
                    fallback_level = "relaxed_airline"
                    fallback_message = "Using available observations for route — no records for selected airline on this date."

            # Step D: Relax cabin_class if still 0
            if total_obs == 0 and cabin_class:
                q_d = build_q(origin, destination, None, None, advance_window, data_mode, None, None)
                cnt_d, avg_d, min_d, max_d = get_agg(q_d)
                if cnt_d > 0:
                    q = q_d
                    total_obs, avg_f, min_f, max_f = cnt_d, avg_d, min_d, max_d
                    is_fallback = True
                    fallback_level = "relaxed_cabin"
                    fallback_message = "Using available observations for route."

            # Step E: Full dataset fallback if still 0
            if total_obs == 0:
                q_e = build_q(None, None, None, None, None, data_mode, None, None)
                cnt_e, avg_e, min_e, max_e = get_agg(q_e)
                if cnt_e > 0:
                    q = q_e
                    total_obs, avg_f, min_f, max_f = cnt_e, avg_e, min_e, max_e
                    is_fallback = True
                    fallback_level = "full_dataset"
                    fallback_message = "Using dataset baseline."

        summary = FareSummaryStats(
            total_observations=total_obs,
            avg_fare=avg_f,
            min_fare=min_f,
            max_fare=max_f,
            is_fallback=is_fallback,
            fallback_level=fallback_level,
            fallback_message=fallback_message,
        )

        # 2. Fare Movement Trend: Complete time-series grouped by travel_date
        trend_q = q
        # If single date was filtered, compute trend across available dates for the route/airline context
        if travel_date_from and travel_date_to and travel_date_from == travel_date_to:
            trend_q = build_q(
                origin,
                destination,
                airline if fallback_level != "relaxed_airline" else None,
                cabin_class if fallback_level not in ("relaxed_airline", "relaxed_cabin") else None,
                advance_window,
                data_mode,
                None,
                None,
            )

        trend_rows = (
            trend_q.with_entities(
                FareObservation.travel_date,
                func.avg(FareObservation.fare).label("avg_fare"),
                func.count(FareObservation.id).label("count"),
            )
            .filter(FareObservation.travel_date.isnot(None))
            .group_by(FareObservation.travel_date)
            .order_by(FareObservation.travel_date.asc())
            .all()
        )
        trend = [
            FareTrendPoint(
                date=str(r[0]),
                avgFare=round(float(r[1])),
                count=int(r[2]),
            )
            for r in trend_rows
            if r[0] is not None and r[1] is not None
        ]

        if len(trend) <= 1 and (origin or destination):
            broad_trend_rows = (
                build_q(origin, destination, None, None, None, data_mode, None, None)
                .with_entities(
                    FareObservation.travel_date,
                    func.avg(FareObservation.fare).label("avg_fare"),
                    func.count(FareObservation.id).label("count"),
                )
                .filter(FareObservation.travel_date.isnot(None))
                .group_by(FareObservation.travel_date)
                .order_by(FareObservation.travel_date.asc())
                .all()
            )
            if broad_trend_rows:
                trend = [
                    FareTrendPoint(
                        date=str(r[0]),
                        avgFare=round(float(r[1])),
                        count=int(r[2]),
                    )
                    for r in broad_trend_rows
                    if r[0] is not None and r[1] is not None
                ]

        # 3. Airline Fare Comparison: All airlines in the filtered subset
        airline_code_upper = func.upper(FareObservation.airline_code).label("airline_code")
        airline_rows = (
            q.with_entities(
                airline_code_upper,
                func.avg(FareObservation.fare).label("avg_fare"),
                func.count(FareObservation.id).label("count"),
            )
            .filter(FareObservation.airline_code.isnot(None))
            .group_by(airline_code_upper)
            .order_by(func.avg(FareObservation.fare).asc())
            .all()
        )
        if len(airline_rows) == 0 and (origin or destination):
            # Relax to route airlines
            airline_rows = (
                build_q(origin, destination, None, None, None, data_mode, None, None)
                .with_entities(
                    airline_code_upper,
                    func.avg(FareObservation.fare).label("avg_fare"),
                    func.count(FareObservation.id).label("count"),
                )
                .filter(FareObservation.airline_code.isnot(None))
                .group_by(airline_code_upper)
                .order_by(func.avg(FareObservation.fare).asc())
                .all()
            )
        airline_comparison = [
            AirlineComparisonItem(
                airlineCode=str(r[0]),
                avgFare=round(float(r[1])),
                count=int(r[2]),
            )
            for r in airline_rows
            if r[0] is not None and r[1] is not None
        ]

        # 4. Route Fare Benchmark: Routes in the filtered subset
        origin_upper = func.upper(FareObservation.origin).label("origin")
        dest_upper = func.upper(FareObservation.destination).label("destination")
        route_rows = (
            q.with_entities(
                origin_upper,
                dest_upper,
                func.avg(FareObservation.fare).label("avg_fare"),
                func.count(FareObservation.id).label("count"),
            )
            .filter(FareObservation.origin.isnot(None), FareObservation.destination.isnot(None))
            .group_by(origin_upper, dest_upper)
            .order_by(func.avg(FareObservation.fare).desc())
            .limit(15)
            .all()
        )
        if len(route_rows) == 0:
            route_rows = (
                build_q(None, None, None, None, None, data_mode, None, None)
                .with_entities(
                    origin_upper,
                    dest_upper,
                    func.avg(FareObservation.fare).label("avg_fare"),
                    func.count(FareObservation.id).label("count"),
                )
                .filter(FareObservation.origin.isnot(None), FareObservation.destination.isnot(None))
                .group_by(origin_upper, dest_upper)
                .order_by(func.avg(FareObservation.fare).desc())
                .limit(15)
                .all()
            )
        route_comparison = [
            RouteComparisonItem(
                route=f"{r[0]}-{r[1]}",
                avgFare=round(float(r[2])),
                count=int(r[3]),
            )
            for r in route_rows
            if r[0] is not None and r[1] is not None and r[2] is not None
        ]

        return FareAnalyticsResponse(
            status="success",
            summary=summary,
            trend=trend,
            airline_comparison=airline_comparison,
            route_comparison=route_comparison,
            exact_match_found=exact_match_found,
            context_note=fallback_message,
        )
    except Exception as exc:
        logger.error("Failed to query fare analytics: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query fare analytics: {exc}",
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
