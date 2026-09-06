"""
backend/app/api/routers/anomalies.py
--------------------------------------
GET /api/anomalies — Phase 3 anomaly detection results.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.db.models import Anomaly
from backend.app.schemas.responses import AnomaliesResponse, AnomalyRecord, PaginationMeta

router = APIRouter(prefix="/api", tags=["Anomalies"])


@router.get("/anomalies", response_model=AnomaliesResponse, summary="Detected fare anomalies")
def list_anomalies(
    route: Optional[str] = Query(None, description="Route code, e.g. DEL-BOM"),
    severity: Optional[str] = Query(None, description="NORMAL / WATCH / HIGH"),
    method: Optional[str] = Query(None, description="IQR or IsolationForest"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> AnomaliesResponse:
    """
    Return anomalous fare observations detected using Phase 3 IQR and Isolation Forest methods.
    """
    q = db.query(Anomaly)

    if route:
        q = q.filter(Anomaly.route == route.upper())
    if severity:
        q = q.filter(Anomaly.severity.ilike(severity))
    if method:
        q = q.filter(Anomaly.method == method)

    total = q.count()
    records = q.order_by(Anomaly.detected_at.desc()).offset(offset).limit(limit).all()

    return AnomaliesResponse(
        data=[AnomalyRecord.model_validate(r) for r in records],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )
