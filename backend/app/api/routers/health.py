"""
backend/app/api/routers/health.py
----------------------------------
GET /health — application health check.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.responses import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """
    Returns application health status, configuration flags.
    Never exposes credentials.
    """
    return HealthResponse(
        status="ok",
        version="4.0",
        demo_mode=settings.DEMO_MODE,
        amadeus_configured=bool(settings.AMADEUS_CLIENT_ID and settings.AMADEUS_CLIENT_SECRET),
    )
