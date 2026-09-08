"""
backend/app/api/routers/index.py
----------------------------------
GET /api/index            — all prototype airfare index records
GET /api/index/{origin}/{destination} — route-specific index
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.db.models import AirfareIndex
from backend.app.schemas.responses import IndexResponse, IndexRecord

router = APIRouter(prefix="/api", tags=["Index"])

_DISCLAIMER = (
    "PROTOTYPE Airfare Price Index only — NOT an official Government of India index. "
    "Computed from available historical fare observations using equal-weight methodology."
)


@router.get("/index", response_model=IndexResponse, summary="Prototype Airfare Price Index")
def list_index(
    route: Optional[str] = Query(None, description="Route filter, e.g. DEL-BOM"),
    airline: Optional[str] = Query(None, description="Airline filter, e.g. 6E or ALL"),
    period: Optional[str] = Query(None, description="Filter by period, e.g. 2022-01"),
    period_type: Optional[str] = Query(None, description="month / quarter / year"),
    frequency: Optional[str] = Query(None, description="daily / weekly / monthly"),
    sub_index: Optional[str] = Query(None, description="COMPOSITE / T+1_SPOT / T+7_WEEK / etc."),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> IndexResponse:
    """
    Return prototype Airfare Price Index records.
    NOT an official Government of India statistical index.
    """
    q = db.query(AirfareIndex)
    if route:
        q = q.filter(AirfareIndex.route == route.upper())
    if airline:
        q = q.filter(AirfareIndex.airline == airline.upper())
    if period:
        q = q.filter(AirfareIndex.period == period)
    if period_type:
        q = q.filter(AirfareIndex.period_type == period_type)
    if frequency:
        q = q.filter(AirfareIndex.frequency == frequency)
    if sub_index:
        q = q.filter(AirfareIndex.sub_index == sub_index)

    total = q.count()
    records = q.order_by(AirfareIndex.period.desc()).offset(offset).limit(limit).all()

    return IndexResponse(
        disclaimer=_DISCLAIMER,
        data=[IndexRecord.model_validate(r) for r in records],
        total=total,
    )


@router.get(
    "/index/{origin}/{destination}",
    response_model=IndexResponse,
    summary="Route-specific Prototype Airfare Price Index",
)
def route_index(
    origin: str,
    destination: str,
    airline: Optional[str] = Query(None, description="Airline code filter e.g. 6E or AI"),
    cabin_class: Optional[str] = Query(None, description="Cabin class filter e.g. Economy"),
    travel_date: Optional[str] = Query(None, description="Travel date YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> IndexResponse:
    """
    Return prototype index for a specific origin-destination route,
    normalized to the route's own reference-period average fare (Base = 100).
    NOT an official Government of India statistical index.
    """
    from datetime import date
    from sqlalchemy import cast, func, String
    from backend.app.db.models import FareObservation

    route_code = f"{origin.upper()}-{destination.upper()}"

    # Filter out anomalous weekly/isolated records (period starting with 'W-' or post-April 2022)
    # that skew the timeline or compare economy-only flights against business-class-heavy baselines.
    records = (
        db.query(AirfareIndex)
        .filter(
            AirfareIndex.route == route_code,
            ~AirfareIndex.period.like("W-%"),
            AirfareIndex.period <= "2022-04-30",
        )
        .order_by(AirfareIndex.period.desc())
        .all()
    )

    if not records:
        records = (
            db.query(AirfareIndex)
            .filter(
                AirfareIndex.route == route_code,
                ~AirfareIndex.period.like("W-%"),
            )
            .order_by(AirfareIndex.period.desc())
            .all()
        )

    if not records:
        aggregate_records = (
            db.query(AirfareIndex)
            .filter(
                AirfareIndex.route == "AGGREGATE",
                ~AirfareIndex.period.like("W-%"),
            )
            .order_by(AirfareIndex.period.desc())
            .all()
        )
        if aggregate_records:
            return IndexResponse(
                disclaimer="Route-specific index unavailable for this sector. Showing national aggregate index baseline.",
                data=[IndexRecord.model_validate(r) for r in aggregate_records],
                total=len(aggregate_records),
            )
        raise HTTPException(
            status_code=404,
            detail=f"No index records found for route {route_code} or AGGREGATE.",
        )

    # Dynamic calculation if airline, cabin_class, or travel_date is specified
    custom_records = []
    if airline or cabin_class or travel_date:
        # 1. Base reference fare from the SAME route in base period (2022-02)
        ref_q = db.query(func.avg(FareObservation.fare)).filter(
            func.upper(FareObservation.origin) == origin.upper(),
            func.upper(FareObservation.destination) == destination.upper(),
            FareObservation.travel_date >= date(2022, 2, 1),
            FareObservation.travel_date <= date(2022, 2, 28),
        )
        if airline:
            ref_q_airl = ref_q.filter(func.upper(FareObservation.airline_code) == airline.upper())
            airl_base = ref_q_airl.scalar()
            if airl_base and airl_base > 0:
                ref_q = ref_q_airl
        if cabin_class:
            ref_q_cabin = ref_q.filter(cast(FareObservation.cabin_class, String).ilike(f"%{cabin_class}%"))
            cabin_base = ref_q_cabin.scalar()
            if cabin_base and cabin_base > 0:
                ref_q = ref_q_cabin

        base_fare_val = ref_q.scalar()
        if not base_fare_val or base_fare_val <= 0:
            base_fare_val = records[0].baseline_fare if records and records[0].baseline_fare else 5000.0

        # 2. Selected / current average fare for the filtered subset
        curr_q = db.query(func.avg(FareObservation.fare), func.count(FareObservation.id)).filter(
            func.upper(FareObservation.origin) == origin.upper(),
            func.upper(FareObservation.destination) == destination.upper(),
        )
        if travel_date:
            try:
                y, m, d = map(int, travel_date.split("-"))
                t_date = date(y, m, d)
                curr_q = curr_q.filter(FareObservation.travel_date == t_date)
            except Exception:
                pass
        if airline:
            curr_q = curr_q.filter(func.upper(FareObservation.airline_code) == airline.upper())
        if cabin_class:
            curr_q = curr_q.filter(cast(FareObservation.cabin_class, String).ilike(f"%{cabin_class}%"))

        curr_res = curr_q.first()
        if curr_res and curr_res[0] and curr_res[1] and curr_res[1] > 0:
            curr_avg = float(curr_res[0])
            # If travel_date is in Base Period (2022-02), normalize exactly to 100.0
            if travel_date and travel_date.startswith("2022-02"):
                idx_val = 100.0
            else:
                idx_val = round((curr_avg / float(base_fare_val)) * 100.0, 2)

            custom_rec = IndexRecord(
                id=0,
                route=route_code,
                airline=airline.upper() if airline else "ALL",
                period=travel_date if travel_date else (records[0].period if records else "2022-04-01"),
                period_type="daily" if travel_date else "month",
                frequency="daily" if travel_date else "monthly",
                sub_index="COMPOSITE",
                avg_fare=round(curr_avg, 2),
                baseline_fare=round(float(base_fare_val), 2),
                index_value=idx_val,
                baseline_period="2022-02",
                observation_count=int(curr_res[1]),
                data_source="APIx Real-Time Airfare Price Index Engine",
            )
            custom_records.append(custom_rec)

    data_to_return = custom_records + [IndexRecord.model_validate(r) for r in records]

    return IndexResponse(
        disclaimer=_DISCLAIMER,
        data=data_to_return,
        total=len(data_to_return),
    )

