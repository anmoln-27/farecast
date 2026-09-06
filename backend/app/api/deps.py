"""
backend/app/api/deps.py
-----------------------
Reusable FastAPI dependencies injected into route handlers.
"""
from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from backend.app.db.base import get_db  # noqa: re-export
from backend.app.core.config import Settings, get_settings

__all__ = ["get_db", "get_settings"]
