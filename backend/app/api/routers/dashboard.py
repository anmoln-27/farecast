"""
backend/app/api/routers/dashboard.py
--------------------------------------
GET /api/dashboard/summary — combined summary for dashboard views.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

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

        # Compute full-dataset fare aggregates (not paginated)
        fare_agg = db.query(
            func.avg(FareObservation.fare),
            func.min(FareObservation.fare),
            func.max(FareObservation.fare),
        ).one()
        avg_fare = float(fare_agg[0]) if fare_agg[0] is not None else None
        min_fare = float(fare_agg[1]) if fare_agg[1] is not None else None
        max_fare = float(fare_agg[2]) if fare_agg[2] is not None else None
    except Exception as exc:
        logger.error("Dashboard summary error: %s", exc)
        fare_count = 0
        data_modes = ["HISTORICAL"]
        avg_fare = None
        min_fare = None
        max_fare = None

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
        avg_fare=avg_fare,
        min_fare=min_fare,
        max_fare=max_fare,
    )


@router.post("/seed-historical", summary="Seed genuine historical dataset into database")
def seed_historical_endpoint(db: Session = Depends(get_db)) -> dict:
    """
    Safely imports the genuine 30,114 historical airfare observations into PostgreSQL.
    Idempotent: skips if already populated.
    """
    from scripts.import_historical_to_postgres import import_genuine_historical_data
    return import_genuine_historical_data(session=db)
