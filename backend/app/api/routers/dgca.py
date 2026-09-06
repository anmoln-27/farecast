"""
backend/app/api/routers/dgca.py
---------------------------------
GET /api/dgca       — list DGCA aviation statistics
GET /api/dgca/summary — aggregated summary
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.db.models import DGCAAviationStat
from backend.app.schemas.responses import DGCAResponse, DGCARecord, PaginationMeta

router = APIRouter(prefix="/api/dgca", tags=["DGCA"])

_DISCLAIMER = (
    "Official DGCA aviation statistics. Represents domestic traffic and capacity data, "
    "NOT airfare/ticket-price data."
)


@router.get("", response_model=DGCAResponse, summary="DGCA aviation statistics")
def list_dgca(
    period: Optional[str] = Query(None, description="Period filter, e.g. 2023-01"),
    airline: Optional[str] = Query(None, description="Airline name filter"),
    origin: Optional[str] = Query(None, description="IATA origin code"),
    destination: Optional[str] = Query(None, description="IATA destination code"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> DGCAResponse:
    """
    Query DGCA domestic aviation statistics (passengers, capacity, load factor).
    This is NOT airfare data.
    """
    q = db.query(DGCAAviationStat)

    if period:
        q = q.filter(DGCAAviationStat.period == period)
    if airline:
        q = q.filter(DGCAAviationStat.airline.ilike(f"%{airline}%"))
    if origin:
        q = q.filter(DGCAAviationStat.origin == origin.upper())
    if destination:
        q = q.filter(DGCAAviationStat.destination == destination.upper())

    total = q.count()
    records = q.order_by(DGCAAviationStat.period.desc()).offset(offset).limit(limit).all()

    return DGCAResponse(
        disclaimer=_DISCLAIMER,
        data=[DGCARecord.model_validate(r) for r in records],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/summary", tags=["DGCA"], summary="DGCA data summary")
def dgca_summary(db: Session = Depends(get_db)):
    """
    Aggregated summary of DGCA records in the database.
    """
    total = db.query(DGCAAviationStat).count()
    periods = (
        db.query(DGCAAviationStat.period)
        .distinct()
        .order_by(DGCAAviationStat.period.desc())
        .limit(12)
        .all()
    )
    return {
        "disclaimer": _DISCLAIMER,
        "total_records": total,
        "latest_periods": [p[0] for p in periods],
        "note": (
            "Load DGCA statistics via: python scripts/load_dgca.py "
            "after placing dgca_stats.csv in data/external/"
        ),
    }
