"""
backend/app/core/config.py
--------------------------
Centralised configuration management using pydantic-settings.
All runtime settings are loaded from environment variables / .env file.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_DEBUG: bool = True
    DEMO_MODE: bool = True           # True = use historical data, skip live APIs

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL_OVERRIDE: Optional[str] = Field(default=None, alias="DATABASE_URL")
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "farecast"
    POSTGRES_USER: str = "farecast_user"
    POSTGRES_PASSWORD: str = "farecast_password"

    @computed_field  # type: ignore[misc]
    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Amadeus ───────────────────────────────────────────────────────────────
    AMADEUS_CLIENT_ID: str = ""
    AMADEUS_CLIENT_SECRET: str = ""
    AMADEUS_HOSTNAME: Literal["test", "production"] = "test"

    @computed_field  # type: ignore[misc]
    @property
    def amadeus_available(self) -> bool:
        return bool(self.AMADEUS_CLIENT_ID and self.AMADEUS_CLIENT_SECRET)

    # ── CORS ──────────────────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
