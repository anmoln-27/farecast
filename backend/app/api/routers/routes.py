"""
backend/app/api/routers/routes.py
-----------------------------------
GET /api/routes — available origin-destination routes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.db.models import Route
from backend.app.schemas.responses import RoutesResponse, RouteRecord

router = APIRouter(prefix="/api", tags=["Routes"])


@router.get("/routes", response_model=RoutesResponse, summary="Available routes")
def list_routes(db: Session = Depends(get_db)) -> RoutesResponse:
    """
    Return all origin-destination routes stored in the database.
    """
    records = db.query(Route).order_by(Route.origin, Route.destination).all()
    return RoutesResponse(
        data=[RouteRecord.model_validate(r) for r in records],
        total=len(records),
    )
