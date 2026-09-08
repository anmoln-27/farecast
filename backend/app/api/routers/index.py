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
    db: Session = Depends(get_db),
) -> IndexResponse:
    """
    Return prototype index for a specific origin-destination route.
    NOT an official Government of India statistical index.
    """
    route_code = f"{origin.upper()}-{destination.upper()}"
    records = (
        db.query(AirfareIndex)
        .filter(AirfareIndex.route == route_code)
        .order_by(AirfareIndex.period.desc())
        .all()
    )

    if not records:
        aggregate_records = (
            db.query(AirfareIndex)
            .filter(AirfareIndex.route == "AGGREGATE")
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

    return IndexResponse(
        disclaimer=_DISCLAIMER,
        data=[IndexRecord.model_validate(r) for r in records],
        total=len(records),
    )
