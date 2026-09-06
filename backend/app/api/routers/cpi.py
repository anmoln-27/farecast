"""
backend/app/api/routers/cpi.py
--------------------------------
GET /api/cpi — MoSPI/CPI reference data.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.db.models import CPIReference
from backend.app.schemas.responses import CPIResponse, CPIRecord

router = APIRouter(prefix="/api/cpi", tags=["CPI"])

_DISCLAIMER = (
    "MoSPI/CPI Transport & Communication index data provided as economic context only. "
    "NOT used as airfare observations or ML training data. "
    "Base year 2012=100."
)


@router.get("", response_model=CPIResponse, summary="CPI/MoSPI reference data")
def list_cpi(db: Session = Depends(get_db)) -> CPIResponse:
    """
    Return MoSPI CPI reference records (Transport & Communication group).
    These are NOT airfare prices — they are macroeconomic reference benchmarks.
    """
    records = db.query(CPIReference).order_by(CPIReference.period.desc()).all()
    return CPIResponse(
        disclaimer=_DISCLAIMER,
        data=[CPIRecord.model_validate(r) for r in records],
        total=len(records),
    )
