"""
scripts/load_kaggle.py
-----------------------
Ingests the Kaggle "Flight Price Prediction" dataset into the
fare_observations table.

Dataset: https://www.kaggle.com/datasets/shubhambathwal/flight-price-prediction
Expected file: data/raw/Clean_Dataset.csv

IMPORTANT:
  - This dataset is HISTORICAL. data_mode = HISTORICAL.
  - Do NOT represent it as live/current pricing.
  - Do NOT fabricate collection timestamps.
  - Use it primarily for ML training and historical fare analysis.

Usage:
  # From project root:
  python scripts/load_kaggle.py

  # Dry run (no DB writes):
  python scripts/load_kaggle.py --dry-run

  # Specify custom path:
  python scripts/load_kaggle.py --path data/raw/Clean_Dataset.csv
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path

# ── path setup so we can import backend modules from project root ─────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from backend.app.services.cleaner import clean_fare_records
from backend.app.services.schema import (
    CITY_TO_IATA,
    FareRecord,
    normalise_airline,
    normalise_city,
)

logger = logging.getLogger(__name__)

DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "raw" / "Clean_Dataset.csv"
SOURCE_NAME = "kaggle"

# ── Column name mapping (Kaggle dataset uses these column headers) ─────────────
# Actual column names from the dataset:
#   Airline, Flight, Source City, Departure Time, Stops,
#   Arrival Time, Destination City, Class, Duration, Days Left, Price
COLUMN_MAP = {
    "Airline": "airline",
    "Flight": "flight_number",
    "Source City": "source_city",
    "Departure Time": "departure_time",
    "Stops": "stops",
    "Arrival Time": "arrival_time",
    "Destination City": "destination_city",
    "Class": "cabin_class",
    "Duration": "duration_raw",
    "Days Left": "days_left",
    "Price": "fare",
}

STOPS_MAP = {
    "zero": 0,
    "one": 1,
    "two or more": 2,
    "non-stop": 0,
    "1 stop": 1,
    "2+ stops": 2,
}


def parse_stops(value) -> int:
    if isinstance(value, int):
        return value
    s = str(value).strip().lower()
    return STOPS_MAP.get(s, 0)


def parse_duration_kaggle(value) -> int | None:
    """Kaggle duration is stored in hours as float, e.g. 2.33 → 140 minutes."""
    try:
        hours = float(value)
        return int(hours * 60)
    except (TypeError, ValueError):
        return None


def load_kaggle(csv_path: Path = DEFAULT_CSV_PATH, dry_run: bool = False) -> dict:
    """
    Load, clean, and (optionally) persist Kaggle fare data.

    Returns a summary dict.
    """
    if not csv_path.exists():
        logger.error(
            f"Kaggle CSV not found at: {csv_path}\n"
            "Please download the dataset from:\n"
            "  https://www.kaggle.com/datasets/shubhambathwal/flight-price-prediction\n"
            "and place 'Clean_Dataset.csv' in data/raw/"
        )
        return {"status": "file_not_found", "path": str(csv_path)}

    logger.info(f"Loading Kaggle dataset from: {csv_path}")
    df = pd.read_csv(csv_path)

    logger.info(f"Raw shape: {df.shape}")
    logger.info(f"Columns: {list(df.columns)}")

    # ── Rename columns ────────────────────────────────────────────────────────
    rename = {k: v for k, v in COLUMN_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    # ── Build FareRecord list ─────────────────────────────────────────────────
    records: list[FareRecord] = []
    for _, row in df.iterrows():
        try:
            fare_val = float(row.get("fare", 0))
            stops_val = parse_stops(row.get("stops", 0))
            duration_min = parse_duration_kaggle(row.get("duration_raw"))
            days_left_val = int(row.get("days_left", 0)) if pd.notna(row.get("days_left")) else None

            rec = FareRecord(
                source=SOURCE_NAME,
                data_mode="HISTORICAL",
                airline_code=str(row.get("airline", "")).strip(),
                flight_number=str(row.get("flight_number", "")).strip() or None,
                origin=str(row.get("source_city", "")).strip(),
                destination=str(row.get("destination_city", "")).strip(),
                travel_date=None,    # Kaggle dataset has no absolute travel date
                booking_date=None,
                departure_time=str(row.get("departure_time", "")).strip() or None,
                arrival_time=str(row.get("arrival_time", "")).strip() or None,
                stops=stops_val,
                duration_minutes=duration_min,
                cabin_class=str(row.get("cabin_class", "Economy")).strip(),
                fare=fare_val,
                currency="INR",
                days_left=days_left_val,
                collected_at=None,  # no fabricated timestamp
            )
            records.append(rec)
        except Exception as exc:
            logger.debug(f"Skipping row due to error: {exc}")
            continue

    # ── Clean ─────────────────────────────────────────────────────────────────
    cleaned, report = clean_fare_records(records, source=SOURCE_NAME)
    logger.info(report.summary())

    # ── Persist ───────────────────────────────────────────────────────────────
    if not dry_run and cleaned:
        _persist(cleaned)

    return {
        "status": "ok",
        "raw_rows": len(df),
        "raw_columns": list(df.columns),
        "records_parsed": len(records),
        "records_cleaned": len(cleaned),
        "cleaning_report": {
            "dropped_missing": report.dropped_missing_required,
            "dropped_bad_fare": report.dropped_impossible_fare,
            "dropped_duplicates": report.dropped_duplicates,
            "dropped_invalid_route": report.dropped_invalid_route,
        },
        "dry_run": dry_run,
    }


def _persist(records: list[FareRecord]) -> None:
    """Bulk-insert cleaned records into PostgreSQL."""
    from backend.app.db.base import SessionLocal
    from backend.app.db.models import FareObservation, DataMode, CabinClass

    session = SessionLocal()()
    try:
        # Clear existing Kaggle records to allow re-runs
        deleted = session.query(FareObservation).filter_by(source="kaggle").delete()
        logger.info(f"Cleared {deleted} existing Kaggle records.")

        batch = []
        for rec in records:
            try:
                dm = DataMode(rec.data_mode)
            except ValueError:
                dm = DataMode.HISTORICAL

            try:
                cc = CabinClass(rec.cabin_class)
            except ValueError:
                cc = CabinClass.ECONOMY

            obs = FareObservation(
                source=rec.source,
                data_mode=dm,
                airline_code=rec.airline_code or None,
                flight_number=rec.flight_number or None,
                origin=rec.origin,
                destination=rec.destination,
                travel_date=rec.travel_date,
                booking_date=rec.booking_date,
                departure_time=rec.departure_time,
                arrival_time=rec.arrival_time,
                stops=rec.stops,
                duration_minutes=rec.duration_minutes,
                cabin_class=cc,
                fare=rec.fare,
                currency=rec.currency,
                days_left=rec.days_left,
                collected_at=rec.collected_at,
            )
            batch.append(obs)

            if len(batch) >= 1000:
                session.bulk_save_objects(batch)
                session.commit()
                batch.clear()

        if batch:
            session.bulk_save_objects(batch)
            session.commit()

        total = session.query(FareObservation).filter_by(source="kaggle").count()
        logger.info(f"Kaggle data persisted. Total Kaggle records in DB: {total}")

    except Exception as exc:
        session.rollback()
        logger.error(f"Persistence failed: {exc}")
        raise
    finally:
        session.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    parser = argparse.ArgumentParser(description="Load Kaggle flight price dataset")
    parser.add_argument("--path", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Parse and clean only; do not write to DB")
    args = parser.parse_args()

    result = load_kaggle(args.path, dry_run=args.dry_run)
    print("\n=== Kaggle Load Summary ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
