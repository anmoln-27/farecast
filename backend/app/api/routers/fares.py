"""
backend/app/api/routers/fares.py
---------------------------------
GET /api/fares — query historical fare observations.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.db.models import FareObservation
from backend.app.schemas.responses import FaresResponse, FareRecord, PaginationMeta

router = APIRouter(prefix="/api", tags=["Fares"])


@router.get("/fares", response_model=FaresResponse, summary="Historical fare observations")
def list_fares(
    origin: Optional[str] = Query(None, description="IATA origin code, e.g. DEL"),
    destination: Optional[str] = Query(None, description="IATA destination code, e.g. BOM"),
    airline: Optional[str] = Query(None, description="Airline code, e.g. 6E"),
    cabin_class: Optional[str] = Query(None, description="Economy / Business"),
    travel_date_from: Optional[date] = Query(None),
    travel_date_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> FaresResponse:
    """
    Query historical airfare observations stored in the database.
    Supports filtering by route, airline, cabin class and date range.
    """
    q = db.query(FareObservation)

    if origin:
        q = q.filter(FareObservation.origin == origin.upper())
    if destination:
        q = q.filter(FareObservation.destination == destination.upper())
    if airline:
        q = q.filter(FareObservation.airline_code == airline.upper())
    if cabin_class:
        q = q.filter(FareObservation.cabin_class.ilike(cabin_class))
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
