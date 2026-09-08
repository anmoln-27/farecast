"""
backend/app/db/init_db.py
--------------------------
Database initialisation: creates all tables and seeds reference data.
Run once before the application starts, or via:
    python -m backend.app.db.init_db
"""
from __future__ import annotations

import logging
from sqlalchemy import inspect, text

from backend.app.db.base import Base, engine
from backend.app.db.models import Airline, CPIReference  # noqa: F401 — imported for metadata

logger = logging.getLogger(__name__)

# ── Canonical airline list for Indian domestic market ────────────────────────
SEED_AIRLINES = [
    {"code": "AI", "name": "Air India"},
    {"code": "6E", "name": "IndiGo"},
    {"code": "SG", "name": "SpiceJet"},
    {"code": "UK", "name": "Vistara"},
    {"code": "G8", "name": "Go First"},
    {"code": "I5", "name": "Air Asia India"},
    {"code": "QP", "name": "Akasa Air"},
    {"code": "IX", "name": "Air India Express"},
    {"code": "9W", "name": "Jet Airways"},
]

# ── MoSPI / CPI reference seed data ─────────────────────────────────────────
SEED_CPI = [
    {
        "indicator": "CPI (Rural+Urban) - Transport & Communication",
        "period": "2022-01",
        "value": 129.8,
        "base_year": "2012",
        "description": "MoSPI CPI Combined index - Transport & Communication group",
    },
    {
        "indicator": "CPI (Rural+Urban) - Transport & Communication",
        "period": "2022-06",
        "value": 132.5,
        "base_year": "2012",
        "description": "MoSPI CPI Combined index - Transport & Communication group",
    },
    {
        "indicator": "CPI (Rural+Urban) - Transport & Communication",
        "period": "2022-12",
        "value": 135.1,
        "base_year": "2012",
        "description": "MoSPI CPI Combined index - Transport & Communication group",
    },
    {
        "indicator": "CPI (Rural+Urban) - Transport & Communication",
        "period": "2023-06",
        "value": 138.4,
        "base_year": "2012",
        "description": "MoSPI CPI Combined index - Transport & Communication group",
    },
]


def migrate_columns() -> None:
    """
    Safely inspect and add any missing columns across SQLite AND PostgreSQL.
    Dialect-agnostic: uses sqlalchemy.inspect() instead of SQLite-only PRAGMAs.
    Never drops data or tables.
    """
    eng = engine()
    with eng.connect() as conn:
        inspector = inspect(conn)
        tables = inspector.get_table_names()

        # 1. fare_observations columns
        if "fare_observations" in tables:
            try:
                existing_cols = {col["name"] for col in inspector.get_columns("fare_observations")}
                fare_cols = [
                    ("flight_number", "VARCHAR(20)"),
                    ("booking_date", "DATE"),
                    ("departure_time", "VARCHAR(20)"),
                    ("arrival_time", "VARCHAR(20)"),
                    ("stops", "INTEGER DEFAULT 0"),
                    ("duration_minutes", "INTEGER"),
                    ("base_fare", "FLOAT"),
                    ("taxes", "FLOAT"),
                    ("udf_charge", "FLOAT"),
                    ("convenience_fee", "FLOAT"),
                    ("total_fare", "FLOAT"),
                    ("advance_window", "VARCHAR(10)"),
                    ("status", "VARCHAR(20) DEFAULT 'AVAILABLE'"),
                    ("days_left", "INTEGER"),
                    ("collected_at", "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP" if conn.dialect.name == "postgresql" else "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                    ("created_at", "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP" if conn.dialect.name == "postgresql" else "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ]
                for col_name, col_type in fare_cols:
                    if col_name not in existing_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE fare_observations ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                            logger.info("Added missing column %s to fare_observations.", col_name)
                        except Exception as exc:
                            logger.warning("Could not add column %s to fare_observations: %s", col_name, exc)
                            conn.rollback()
            except Exception as exc:
                logger.warning("Failed inspecting fare_observations columns: %s", exc)

        # 2. airfare_index columns
        if "airfare_index" in tables:
            try:
                existing_cols = {col["name"] for col in inspector.get_columns("airfare_index")}
                index_cols = [
                    ("frequency", "VARCHAR(10) DEFAULT 'monthly'"),
                    ("index_formula", "VARCHAR(30) DEFAULT 'Laspeyres'"),
                    ("sub_index", "VARCHAR(20) DEFAULT 'COMPOSITE'"),
                    ("dgca_weight", "FLOAT"),
                ]
                for col_name, col_type in index_cols:
                    if col_name not in existing_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE airfare_index ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                            logger.info("Added missing column %s to airfare_index.", col_name)
                        except Exception as exc:
                            logger.warning("Could not add column %s to airfare_index: %s", col_name, exc)
                            conn.rollback()
            except Exception as exc:
                logger.warning("Failed inspecting airfare_index columns: %s", exc)

        # 3. PostgreSQL ENUM values safety
        if conn.dialect.name == "postgresql":
            try:
                conn.execute(text("""
                DO $$ BEGIN
                    ALTER TYPE datamode ADD VALUE IF NOT EXISTS 'LIVE';
                EXCEPTION
                    WHEN duplicate_object THEN null;
                    WHEN undefined_object THEN null;
                END $$;
                DO $$ BEGIN
                    ALTER TYPE datamode ADD VALUE IF NOT EXISTS 'HISTORICAL';
                EXCEPTION
                    WHEN duplicate_object THEN null;
                    WHEN undefined_object THEN null;
                END $$;
                DO $$ BEGIN
                    ALTER TYPE datamode ADD VALUE IF NOT EXISTS 'DEMO';
                EXCEPTION
                    WHEN duplicate_object THEN null;
                    WHEN undefined_object THEN null;
                END $$;
                """))
                conn.commit()
            except Exception as exc:
                logger.warning("PostgreSQL enum check: %s", exc)
                conn.rollback()


def create_tables() -> None:
    """Create all tables defined in the ORM models."""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine())
    migrate_columns()
    logger.info("Tables created and migrated successfully.")


def seed_airlines(session) -> None:
    """Insert canonical airline records if not already present."""
    from backend.app.db.models import Airline
    for airline_data in SEED_AIRLINES:
        existing = session.query(Airline).filter_by(code=airline_data["code"]).first()
        if not existing:
            session.add(Airline(**airline_data))
    session.commit()
    logger.info("Airline seed data loaded.")


def seed_cpi_reference(session) -> None:
    """Insert CPI reference records if not already present."""
    from backend.app.db.models import CPIReference
    existing_count = session.query(CPIReference).count()
    if existing_count == 0:
        for cpi_data in SEED_CPI:
            session.add(CPIReference(source="MoSPI", **cpi_data))
        session.commit()
        logger.info("CPI reference seed data loaded.")
    else:
        logger.info(f"CPI reference already has {existing_count} records — skipping seed.")


def init_db() -> None:
    """Full database initialisation: tables + seed data."""
    from backend.app.db.base import SessionLocal
    create_tables()
    db = SessionLocal()()
    try:
        seed_airlines(db)
        seed_cpi_reference(db)
        # Verify connectivity
        db.execute(text("SELECT 1"))
        logger.info("Database initialisation complete.")
    except Exception as exc:
        logger.error(f"Database initialisation failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
