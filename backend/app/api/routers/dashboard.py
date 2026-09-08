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
    try:
        fare_count = db.query(FareObservation).count()
        modes = db.query(distinct(FareObservation.data_mode)).all()
        data_modes = [m[0].value if hasattr(m[0], "value") else str(m[0]) for m in modes]
    except Exception as exc:
        fare_count = 0
        data_modes = ["HISTORICAL"]

    route_count = db.query(Route).count()
    airline_count = db.query(Airline).count()
    anomaly_count = db.query(Anomaly).count()
    index_count = db.query(AirfareIndex).count()
    dgca_count = db.query(DGCAAviationStat).count()
    cpi_count = db.query(CPIReference).count()

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


@router.post("/seed-historical", summary="Seed genuine historical dataset into database")
def seed_historical_endpoint(db: Session = Depends(get_db)) -> dict:
    """
    Safely imports the genuine 30,114 historical airfare observations into PostgreSQL.
    Idempotent: skips if already populated.
    """
    from scripts.import_historical_to_postgres import import_genuine_historical_data
    return import_genuine_historical_data(session=db)
