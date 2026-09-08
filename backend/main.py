"""
backend/main.py
----------------
FastAPI application factory for FARECAST — Airfare Intelligence India.

Phase 4: REST API + Amadeus live integration.

Start with:
    uvicorn backend.main:app --reload
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import get_settings
from backend.app.core.logging_config import setup_logging

# Routers
from backend.app.api.routers import (
    health,
    fares,
    routes,
    airlines,
    index,
    prediction,
    anomalies,
    dgca,
    cpi,
    dashboard,
    live,
    nso_rbi,
    scrapers,
)

setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()


def create_app() -> FastAPI:
    """Application factory — returns configured FastAPI instance."""
    app = FastAPI(
        title="FARECAST — Airfare Intelligence India",
        description=(
            "Prototype airfare analytics and prediction API for Indian domestic aviation.\n\n"
            "**Data Disclaimer:** The Prototype Airfare Price Index is NOT an official "
            "Government of India statistical index. Prediction outputs are based on historical "
            "data patterns; actual fares may differ significantly.\n\n"
            "**Amadeus Coverage:** Live search via Amadeus does not cover every Indian airline "
            "or route."
        ),
        version="4.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(fares.router)
    app.include_router(routes.router)
    app.include_router(airlines.router)
    app.include_router(index.router)
    app.include_router(prediction.router)
    app.include_router(anomalies.router)
    app.include_router(dgca.router)
    app.include_router(cpi.router)
    app.include_router(dashboard.router)
    app.include_router(live.router)
    app.include_router(nso_rbi.router)
    app.include_router(scrapers.router)

    @app.on_event("startup")
    def on_startup():
        """Ensure database schema is up to date and all required columns exist."""
        try:
            from backend.app.db.init_db import create_tables
            create_tables()
            logger.info("Startup database tables & columns verified.")
        except Exception as exc:
            logger.warning("Startup database check warning: %s", exc)

    logger.info(
        "FARECAST API started | DEMO_MODE=%s | Ignav=%s | Amadeus=%s",
        settings.DEMO_MODE,
        "configured" if settings.ignav_available else "not configured",
        "configured" if (settings.AMADEUS_CLIENT_ID and settings.AMADEUS_CLIENT_SECRET) else "not configured",
    )

    return app


app = create_app()
