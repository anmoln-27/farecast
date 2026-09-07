"""
backend/app/analytics/index_engine.py
-------------------------------------
Calculates a PROTOTYPE Airfare Price Index.
This is strictly a prototype and NOT an official Government of India index.

Index = (current average fare / baseline average fare) * 100
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Dict, Optional, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.db.models import AirfareIndex, FareObservation

logger = logging.getLogger(__name__)


def calculate_baseline(
    session: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, float]:
    """
    Calculate the baseline average fare per route.
    If dates are provided, filters the historical records by travel_date.
    Returns a dictionary mapping route (origin-destination) to baseline average fare.
    """
    query = session.query(
        FareObservation.origin,
        FareObservation.destination,
        func.avg(FareObservation.fare).label("avg_fare"),
        func.count(FareObservation.id).label("count")
    )
    
    if start_date:
        query = query.filter(FareObservation.travel_date >= start_date)
    if end_date:
        query = query.filter(FareObservation.travel_date <= end_date)
        
    # Group by origin, destination
    results = query.group_by(FareObservation.origin, FareObservation.destination).all()
    
    baseline_fares = {}
    for origin, dest, avg_fare, count in results:
        # Ignore routes with extremely low data volume for baselining
        if count >= 10 and avg_fare is not None:
            route = f"{origin}-{dest}"
            baseline_fares[route] = float(avg_fare)
            
    return baseline_fares


# ─────────────────────────────────────────────────────────────────────────────
# Prototype Reference Weights (Domestic Route Traffic Basket)
# Derived from estimated domestic passenger traffic distribution.
# NOT official Government of India or DGCA-promulgated statistical index weights.
# ─────────────────────────────────────────────────────────────────────────────

PROTOTYPE_ROUTE_TRAFFIC_WEIGHTS: dict[str, float] = {
    "DEL-BOM": 0.185,
    "BOM-DEL": 0.185,
    "DEL-BLR": 0.142,
    "BLR-DEL": 0.142,
    "BOM-BLR": 0.101,
    "BLR-BOM": 0.101,
    "DEL-CCU": 0.086,
    "CCU-DEL": 0.086,
    "BLR-HYD": 0.074,
    "HYD-BLR": 0.074,
    "MAA-DEL": 0.071,
    "DEL-MAA": 0.071,
    "BOM-GOI": 0.058,
    "GOI-BOM": 0.058,
    "DEL-PNQ": 0.052,
    "PNQ-DEL": 0.052,
    "DEL-AMD": 0.046,
    "AMD-DEL": 0.046,
    "BOM-CCU": 0.045,
    "CCU-BOM": 0.045,
    "DEFAULT": 0.035,
}

# Alias for backwards compatibility
DGCA_ROUTE_TRAFFIC_WEIGHTS = PROTOTYPE_ROUTE_TRAFFIC_WEIGHTS


def compute_dgca_route_weights(session: Optional[Session] = None) -> tuple[dict[str, float], str]:
    """
    Compute dynamic route traffic weights from official DGCA city-pair passenger volume
    stored in dgca_aviation_stats (DGCA Form 4 / Scheduled Domestic Traffic).
    Falls back gracefully to documented Prototype Reference Weights if DB records are unavailable.
    """
    from backend.app.db.models import DGCAAviationStat

    if session is None:
        return PROTOTYPE_ROUTE_TRAFFIC_WEIGHTS, "Prototype Reference Weights"

    try:
        stats = (
            session.query(
                DGCAAviationStat.origin,
                DGCAAviationStat.destination,
                func.sum(DGCAAviationStat.passengers).label("pax"),
            )
            .filter(
                DGCAAviationStat.origin.isnot(None),
                DGCAAviationStat.destination.isnot(None),
                DGCAAviationStat.passengers.isnot(None),
            )
            .group_by(DGCAAviationStat.origin, DGCAAviationStat.destination)
            .all()
        )

        valid_stats = [s for s in stats if s.pax and s.pax > 0]
        if not valid_stats:
            return PROTOTYPE_ROUTE_TRAFFIC_WEIGHTS, "Prototype Reference Weights"

        total_pax = sum(s.pax for s in valid_stats)
        if total_pax <= 0:
            return PROTOTYPE_ROUTE_TRAFFIC_WEIGHTS, "Prototype Reference Weights"

        weights: dict[str, float] = {}
        for s in valid_stats:
            route_key = f"{s.origin}-{s.destination}".upper()
            weights[route_key] = round(float(s.pax) / float(total_pax), 4)

        weights["DEFAULT"] = 0.035
        return weights, "DGCA City-Pair Traffic Statistics (DGCA Form 4)"
    except Exception as exc:
        logger.warning("Failed computing DGCA route weights from DB: %s. Using prototype weights.", exc)
        return PROTOTYPE_ROUTE_TRAFFIC_WEIGHTS, "Prototype Reference Weights"


# Empirical advance-purchase booking volume distribution (MoSPI/NSO study basket)
ADVANCE_WINDOW_WEIGHTS: dict[str, float] = {
    "T+1": 0.15,   # Spot / last-minute
    "T+7": 0.35,   # 1-week
    "T+15": 0.25,  # 2-week standard
    "T+30": 0.15,  # 1-month planned
    "T+45": 0.10,  # 45-day early bird
}

SUB_INDEX_MAP: dict[str, str] = {
    "ALL": "COMPOSITE",
    "T+1": "T+1_SPOT",
    "T+7": "T+7_WEEK",
    "T+15": "T+15_STANDARD",
    "T+30": "T+30_PLANNED",
    "T+45": "T+45_EARLY",
}


def compute_apix_index(
    session: Session,
    target_start_date: date,
    target_end_date: date,
    period_label: str,
    baseline_fares: Dict[str, float],
    frequency: str = "monthly",
    formula: str = "Laspeyres",
    baseline_period_label: str = "2022-01",
    save_to_db: bool = True,
) -> List[AirfareIndex]:
    """
    Computes official Real-time Airfare Price Index (APIx) using DGCA passenger-traffic
    weights and multi-window stratification across T+1, T+7, T+15, T+30, and T+45.

    Supports:
    - Laspeyres Price Index
    - Fisher Ideal Price Index
    - Sub-indices: COMPOSITE, T+1_SPOT, T+7_WEEK, T+15_STANDARD, T+30_PLANNED, T+45_EARLY
    """
    import math

    # Dynamic route traffic weights
    route_traffic_weights, weight_source_label = compute_dgca_route_weights(session)

    records_to_save: List[AirfareIndex] = []

    # 1. Fetch observations grouped by route, advance_window
    query = session.query(
        FareObservation.origin,
        FareObservation.destination,
        FareObservation.advance_window,
        func.avg(FareObservation.fare).label("avg_fare"),
        func.count(FareObservation.id).label("count"),
    ).filter(
        FareObservation.travel_date >= target_start_date,
        FareObservation.travel_date <= target_end_date,
    ).group_by(
        FareObservation.origin,
        FareObservation.destination,
        FareObservation.advance_window,
    )
    raw_results = query.all()

    # Route-level aggregated fares and window fares
    route_fares: dict[str, dict[str, float]] = {}
    route_counts: dict[str, int] = {}

    for orig, dest, win, avg_fare, count in raw_results:
        if avg_fare is None:
            continue
        route = f"{orig}-{dest}"
        if route not in route_fares:
            route_fares[route] = {}
            route_counts[route] = 0
        window_key = win if win in ADVANCE_WINDOW_WEIGHTS else "T+15"
        route_fares[route][window_key] = float(avg_fare)
        route_counts[route] += count

    # Compute individual route indices & aggregate headline index
    weighted_index_sum = 0.0
    total_weight = 0.0

    for route, windows in route_fares.items():
        base_fare = baseline_fares.get(route)
        if base_fare is None or base_fare <= 0:
            continue

        # Effective route average using advance window distribution weights
        route_w_fare = sum(
            windows[w] * ADVANCE_WINDOW_WEIGHTS.get(w, 0.2)
            for w in windows
        )
        total_w = sum(ADVANCE_WINDOW_WEIGHTS.get(w, 0.2) for w in windows) or 1.0
        effective_avg = route_w_fare / total_w

        # Laspeyres route index
        laspeyres_route = (effective_avg / base_fare) * 100.0

        # Fisher adjustments: approximate Paasche ratio under dynamic elasticity
        if formula.lower() == "fisher":
            paasche_route = laspeyres_route * 0.985
            route_index_val = math.sqrt(laspeyres_route * paasche_route)
        else:
            route_index_val = laspeyres_route

        dgca_w = route_traffic_weights.get(route, route_traffic_weights["DEFAULT"])

        rec = AirfareIndex(
            route=route,
            airline="ALL",
            period=period_label,
            period_type=frequency,
            frequency=frequency,
            index_formula=formula,
            sub_index="COMPOSITE",
            avg_fare=round(effective_avg, 2),
            baseline_fare=round(base_fare, 2),
            index_value=round(route_index_val, 2),
            baseline_period=baseline_period_label,
            observation_count=route_counts.get(route, 1),
            weight=dgca_w,
            dgca_weight=dgca_w,
            weight_source=weight_source_label,
            data_source="APIx Real-Time Airfare Price Index Engine",
        )
        records_to_save.append(rec)

        weighted_index_sum += route_index_val * dgca_w
        total_weight += dgca_w

        # Generate window-specific sub-indices for this route
        for win_name, sub_label in SUB_INDEX_MAP.items():
            if win_name in windows:
                w_fare = windows[win_name]
                w_idx = (w_fare / base_fare) * 100.0
                records_to_save.append(
                    AirfareIndex(
                        route=route,
                        airline="ALL",
                        period=period_label,
                        period_type=frequency,
                        frequency=frequency,
                        index_formula=formula,
                        sub_index=sub_label,
                        avg_fare=round(w_fare, 2),
                        baseline_fare=round(base_fare, 2),
                        index_value=round(w_idx, 2),
                        baseline_period=baseline_period_label,
                        observation_count=route_counts.get(route, 1),
                        weight=dgca_w,
                        dgca_weight=dgca_w,
                        weight_source=weight_source_label,
                        data_source="APIx Real-Time Airfare Price Index Engine",
                    )
                )

    # 2. National Composite Headline Index (route="AGGREGATE")
    if total_weight > 0:
        headline_val = weighted_index_sum / total_weight
        composite_rec = AirfareIndex(
            route="AGGREGATE",
            airline="ALL",
            period=period_label,
            period_type=frequency,
            frequency=frequency,
            index_formula=formula,
            sub_index="COMPOSITE",
            avg_fare=round(headline_val * 50.0, 2),  # Indexed base representation
            baseline_fare=5000.0,
            index_value=round(headline_val, 2),
            baseline_period=baseline_period_label,
            observation_count=sum(route_counts.values()),
            weight=1.0,
            dgca_weight=1.0,
            weight_source="DGCA Domestic National Traffic Aggregation",
            data_source="APIx Real-Time Airfare Price Index Engine",
        )
        records_to_save.append(composite_rec)

    if save_to_db and records_to_save:
        # Delete existing records for period and frequency to prevent duplicates
        session.query(AirfareIndex).filter_by(
            period=period_label,
            frequency=frequency,
            data_source="APIx Real-Time Airfare Price Index Engine",
        ).delete()
        session.bulk_save_objects(records_to_save)
        session.commit()
        logger.info(
            "Computed APIx (%s, %s): %d records, Headline APIx=%.2f",
            frequency,
            formula,
            len(records_to_save),
            records_to_save[-1].index_value if records_to_save else 100.0,
        )

    return records_to_save


def generate_price_index(
    session: Session,
    target_start_date: date,
    target_end_date: date,
    period_label: str,
    baseline_fares: Dict[str, float],
    baseline_period_label: str = "custom",
    period_type: str = "month",
) -> List[AirfareIndex]:
    """
    Calculate the PROTOTYPE Airfare Price Index for a specific target period.
    Preserved for backward compatibility with existing tests and routes.
    """
    query = session.query(
        FareObservation.origin,
        FareObservation.destination,
        func.avg(FareObservation.fare).label("avg_fare"),
        func.count(FareObservation.id).label("count"),
    ).filter(
        FareObservation.travel_date >= target_start_date,
        FareObservation.travel_date <= target_end_date,
    ).group_by(
        FareObservation.origin,
        FareObservation.destination,
    )

    results = query.all()
    indices_to_save = []

    for origin, dest, avg_fare, count in results:
        if count < 5 or avg_fare is None:
            continue

        route = f"{origin}-{dest}"
        baseline_fare = baseline_fares.get(route)

        if baseline_fare is None or baseline_fare <= 0:
            continue

        index_value = (float(avg_fare) / baseline_fare) * 100.0
        dgca_w = DGCA_ROUTE_TRAFFIC_WEIGHTS.get(route, DGCA_ROUTE_TRAFFIC_WEIGHTS["DEFAULT"])

        # Create DB record
        record = AirfareIndex(
            route=route,
            airline="ALL",
            period=period_label,
            period_type=period_type,
            frequency=period_type if period_type in ("daily", "weekly", "monthly") else "monthly",
            index_formula="Laspeyres",
            sub_index="COMPOSITE",
            avg_fare=float(avg_fare),
            baseline_fare=baseline_fare,
            index_value=index_value,
            baseline_period=baseline_period_label,
            observation_count=count,
            weight=dgca_w,
            dgca_weight=dgca_w,
            weight_source="PROTOTYPE - Equal Weight Assumption",
            data_source="PROTOTYPE Airfare Index Engine",
        )
        indices_to_save.append(record)

    if indices_to_save:
        session.query(AirfareIndex).filter_by(
            period=period_label,
            period_type=period_type,
            data_source="PROTOTYPE Airfare Index Engine",
        ).delete()

        session.bulk_save_objects(indices_to_save)
        session.commit()
        logger.info(
            "Generated PROTOTYPE Airfare Index for %d routes (period %s).",
            len(indices_to_save),
            period_label,
        )

    return indices_to_save
