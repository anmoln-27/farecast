"""
backend/app/api/routers/airlines.py
-------------------------------------
GET /api/airlines — available airlines.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.db.models import Airline
from backend.app.schemas.responses import AirlinesResponse, AirlineRecord

router = APIRouter(prefix="/api", tags=["Airlines"])


@router.get("/airlines", response_model=AirlinesResponse, summary="Available airlines")
def list_airlines(db: Session = Depends(get_db)) -> AirlinesResponse:
    """
    Return all airline records from the canonical seed list.
    """
    records = db.query(Airline).order_by(Airline.code).all()
    return AirlinesResponse(
        data=[AirlineRecord.model_validate(r) for r in records],
        total=len(records),
    )
