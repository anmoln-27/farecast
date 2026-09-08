"""
backend/app/api/routers/dashboard.py
--------------------------------------
GET /api/dashboard/summary — combined summary for dashboard views.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import distinct
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_settings
from backend.app.core.config import Settings
from backend.app.db.models import (
    Airline, AirfareIndex, Anomaly, CPIReference,
    DGCAAviationStat, FareObservation, Route,
)
from backend.app.schemas.responses import DashboardSummary

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary, summary="Dashboard summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DashboardSummary:
    """
    Aggregated summary of all Phase 1–3 data suitable for a dashboard view.
    """
    fare_count = db.query(FareObservation).count()
    route_count = db.query(Route).count()
    airline_count = db.query(Airline).count()
    anomaly_count = db.query(Anomaly).count()
    index_count = db.query(AirfareIndex).count()
    dgca_count = db.query(DGCAAviationStat).count()
    cpi_count = db.query(CPIReference).count()

    modes = (
        db.query(distinct(FareObservation.data_mode))
        .all()
    )
    data_modes = [m[0].value if hasattr(m[0], "value") else str(m[0]) for m in modes]

    return DashboardSummary(
        total_fare_observations=fare_count,
        total_routes=route_count,
        total_airlines=airline_count,
        total_anomalies=anomaly_count,
        total_index_records=index_count,
        total_dgca_records=dgca_count,
        total_cpi_records=cpi_count,
        demo_mode=settings.DEMO_MODE,
        amadeus_configured=bool(
            settings.AMADEUS_CLIENT_ID and settings.AMADEUS_CLIENT_SECRET
        ),
        ignav_configured=settings.ignav_available,
        data_modes_present=data_modes,
    )
