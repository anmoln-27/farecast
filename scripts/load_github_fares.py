"""
scripts/load_github_fares.py
-----------------------------
Ingests the GitHub full_fare.csv (2022-2023 historical fare observations)
from: https://github.com/Avij112/flight-fare-analysis

Expected file: data/raw/full_fare.csv

IMPORTANT:
  - This dataset is HISTORICAL. data_mode = HISTORICAL.
  - Use for historical trend analysis, route-level analysis, index validation.
  - Do NOT treat interpolated years as actual observed airfare data.
  - Clearly label this source as HISTORICAL throughout.

Usage:
  python scripts/load_github_fares.py
  python scripts/load_github_fares.py --dry-run
  python scripts/load_github_fares.py --path data/raw/full_fare.csv
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from backend.app.services.cleaner import clean_fare_records
from backend.app.services.schema import FareRecord, normalise_airline, normalise_city

logger = logging.getLogger(__name__)

DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "raw" / "full_fare.csv"
SOURCE_NAME = "github_full_fare"

AIRLINE_TO_IATA = {
    "indigo": "6E",
    "vistara": "UK",
    "air india": "AI",
    "airindia": "AI",
    "spicejet": "SG",
    "airasia": "I5",
    "air asia": "I5",
    "go first": "G8",
    "akasa air": "QP",
}


def _detect_columns(df: pd.DataFrame) -> dict:
    """
    Attempt to auto-detect relevant columns from the GitHub fare CSV.
    The exact schema of full_fare.csv may vary, so we try common names.
    Returns a mapping of our field names → actual column names.
    """
    cols = {c.lower().strip(): c for c in df.columns}

    mapping = {}

    # Airline
    for candidate in ["airline", "carrier", "airline_name"]:
        if candidate in cols:
            mapping["airline"] = cols[candidate]
            break

    # Origin
    for candidate in ["origin", "source", "from", "dep_city", "source_city"]:
        if candidate in cols:
            mapping["origin"] = cols[candidate]
            break

    # Destination
    for candidate in ["destination", "dest", "to", "arr_city", "destination_city"]:
        if candidate in cols:
            mapping["destination"] = cols[candidate]
            break

    # Fare / Price
    for candidate in ["fare", "price", "ticket_price", "amount"]:
        if candidate in cols:
            mapping["fare"] = cols[candidate]
            break

    # Stops
    for candidate in ["stops", "num_stops", "stopovers"]:
        if candidate in cols:
            mapping["stops"] = cols[candidate]
            break

    # Duration
    for candidate in ["duration", "flight_duration", "travel_time", "duration_hours"]:
        if candidate in cols:
            mapping["duration"] = cols[candidate]
            break

    # Class
    for candidate in ["class", "cabin_class", "travel_class", "fare_class"]:
        if candidate in cols:
            mapping["cabin_class"] = cols[candidate]
            break

    # Date
    for candidate in ["date", "travel_date", "journey_date", "dep_date", "departure_date"]:
        if candidate in cols:
            mapping["travel_date"] = cols[candidate]
            break

    # Days left
    for candidate in ["days_left", "days_to_departure", "advance_days"]:
        if candidate in cols:
            mapping["days_left"] = cols[candidate]
            break

    # Departure time
    for candidate in ["dep_time", "departure_time", "dep_hour"]:
        if candidate in cols:
            mapping["departure_time"] = cols[candidate]
            break

    # Arrival time
    # Route (combined origin/destination)
    for candidate in ["route", "sector", "pair"]:
        if candidate in cols:
            mapping["route"] = cols[candidate]
            break

    # Direction
    for candidate in ["direction", "dir"]:
        if candidate in cols:
            mapping["direction"] = cols[candidate]
            break

    # Year
    for candidate in ["year", "yr"]:
        if candidate in cols:
            mapping["year"] = cols[candidate]
            break

    return mapping


def load_github_fares(csv_path: Path = DEFAULT_CSV_PATH, dry_run: bool = False) -> dict:
    """
    Load, clean, and (optionally) persist GitHub full_fare.csv.

    Returns a summary dict.
    """
    if not csv_path.exists():
        logger.error(
            f"GitHub full_fare.csv not found at: {csv_path}\n"
            "Please download from:\n"
            "  https://github.com/Avij112/flight-fare-analysis\n"
            "and place 'full_fare.csv' in data/raw/"
        )
        return {"status": "file_not_found", "path": str(csv_path)}

    logger.info(f"Loading GitHub fare data from: {csv_path}")
    df = pd.read_csv(csv_path, low_memory=False, encoding="utf-8")

    logger.info(f"Raw shape: {df.shape}")
    logger.info(f"Columns detected: {list(df.columns)}")

    col_map = _detect_columns(df)
    logger.info(f"Column mapping resolved: {col_map}")

    if "fare" not in col_map:
        logger.error("Cannot find a fare/price column. Aborting.")
        return {"status": "column_error", "columns": list(df.columns)}

    # ── Build FareRecord list ─────────────────────────────────────────────────
    records: list[FareRecord] = []

    for _, row in df.iterrows():
        try:
            fare_raw = row.get(col_map["fare"])
            if pd.isna(fare_raw):
                continue
            fare_val = float(str(fare_raw).replace(",", "").strip())

            origin = str(row.get(col_map.get("origin", ""), "")).strip()
            destination = str(row.get(col_map.get("destination", ""), "")).strip()

            if (not origin or not destination) and "route" in col_map:
                raw_route = str(row.get(col_map["route"], "")).strip()
                sep = "↔" if "↔" in raw_route else ("-" if "-" in raw_route else None)
                if sep and sep in raw_route:
                    parts = [p.strip() for p in raw_route.split(sep)]
                    if len(parts) == 2:
                        direction = str(row.get(col_map.get("direction", ""), "→")).strip()
                        if direction in ("←", "<-", "inbound", "return"):
                            origin, destination = parts[1], parts[0]
                        else:
                            origin, destination = parts[0], parts[1]

            raw_airline = str(row.get(col_map.get("airline", ""), "")).strip()
            airline_code = AIRLINE_TO_IATA.get(raw_airline.lower(), raw_airline)

            # Travel date
            travel_date = None
            if "travel_date" in col_map:
                raw_date = row.get(col_map["travel_date"])
                if pd.notna(raw_date):
                    try:
                        travel_date = pd.to_datetime(raw_date).date()
                    except Exception:
                        travel_date = None
            elif "year" in col_map:
                raw_yr = row.get(col_map["year"])
                if pd.notna(raw_yr):
                    try:
                        yr = int(float(raw_yr))
                        travel_date = date(yr, 6, 15)
                    except Exception:
                        travel_date = None

            stops_raw = row.get(col_map.get("stops", ""), 0)
            try:
                stops_val = int(float(str(stops_raw)))
            except (TypeError, ValueError):
                stops_val = 0

            dur_raw = row.get(col_map.get("duration", ""))
            duration_min = None
            if dur_raw is not None and pd.notna(dur_raw):
                try:
                    hrs = float(str(dur_raw).replace("h", "").replace("m", "").strip())
                    duration_min = int(hrs * 60) if hrs < 24 else int(hrs)
                except ValueError:
                    pass

            cabin_raw = str(row.get(col_map.get("cabin_class", ""), "Economy")).strip()
            days_left_raw = row.get(col_map.get("days_left", ""))
            days_left = 30  # standard reference lead time
            if days_left_raw is not None and pd.notna(days_left_raw):
                try:
                    days_left = int(float(days_left_raw))
                except (TypeError, ValueError):
                    days_left = 30

            dep_time = str(row.get(col_map.get("departure_time", ""), "")).strip() or None
            arr_time = str(row.get(col_map.get("arrival_time", ""), "")).strip() or None

            rec = FareRecord(
                source=SOURCE_NAME,
                data_mode="HISTORICAL",
                airline_code=airline_code or None,
                origin=origin,
                destination=destination,
                travel_date=travel_date,
                departure_time=dep_time,
                arrival_time=arr_time,
                stops=stops_val,
                duration_minutes=duration_min,
                cabin_class=cabin_raw,
                fare=fare_val,
                total_fare=fare_val,
                currency="INR",
                days_left=days_left,
                advance_window="T+30",
                status="AVAILABLE",
            )
            records.append(rec)

        except Exception as exc:
            logger.debug(f"Skipping row: {exc}")
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
        "column_mapping": col_map,
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
    from backend.app.db.base import SessionLocal
    from backend.app.db.models import FareObservation, DataMode, CabinClass

    session = SessionLocal()()
    try:
        deleted = session.query(FareObservation).filter_by(source=SOURCE_NAME).delete()
        logger.info(f"Cleared {deleted} existing GitHub fare records.")

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
                airline_code=rec.airline_code,
                origin=rec.origin,
                destination=rec.destination,
                travel_date=rec.travel_date,
                departure_time=rec.departure_time,
                arrival_time=rec.arrival_time,
                stops=rec.stops,
                duration_minutes=rec.duration_minutes,
                cabin_class=cc,
                fare=rec.fare,
                total_fare=rec.total_fare,
                currency=rec.currency,
                days_left=rec.days_left,
                advance_window=rec.advance_window,
                status=rec.status or "AVAILABLE",
            )
            batch.append(obs)

            if len(batch) >= 1000:
                session.bulk_save_objects(batch)
                session.commit()
                batch.clear()

        if batch:
            session.bulk_save_objects(batch)
            session.commit()

        total = session.query(FareObservation).filter_by(source=SOURCE_NAME).count()
        logger.info(f"GitHub fare data persisted. Total records in DB: {total}")

    except Exception as exc:
        session.rollback()
        logger.error(f"Persistence failed: {exc}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    parser = argparse.ArgumentParser(description="Load GitHub full_fare.csv")
    parser.add_argument("--path", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = load_github_fares(args.path, dry_run=args.dry_run)
    print("\n=== GitHub Fares Load Summary ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
