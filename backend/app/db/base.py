"""
backend/app/db/base.py
----------------------
SQLAlchemy declarative base and engine factory.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def get_engine(echo: bool = False):
    settings = get_settings()
    url = settings.DATABASE_URL
    if "sqlite" in url:
        return create_engine(
            url,
            echo=echo,
            connect_args={"check_same_thread": False},
        )
    return create_engine(
        url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


def get_session_factory(engine=None):
    if engine is None:
        engine = get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Module-level singletons (lazy; created on first use)
_engine = None
_SessionLocal = None


def engine():
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine


def SessionLocal():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = get_session_factory(engine())
    return _SessionLocal


def get_db():
    """FastAPI dependency — yields a DB session and closes it on exit."""
    db = SessionLocal()()
    try:
        yield db
    finally:
        db.close()
