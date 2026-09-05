"""
scripts/load_dgca.py
---------------------
Loads DGCA aviation statistics into the dgca_aviation_stats table.

DGCA is NOT a ticket-fare source.
Use this data for: domestic passenger traffic, flights operated, seats/capacity,
route activity, and aviation market context.

Data file: data/external/dgca_stats.csv (manually placed)

Expected columns (flexible; auto-detected):
  period, airline, origin, destination, passengers,
  flights_operated, seats_offered, load_factor

Usage:
  python scripts/load_dgca.py
  python scripts/load_dgca.py --dry-run
  python scripts/load_dgca.py --path data/external/dgca_stats.csv
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "external" / "dgca_stats.csv"


def load_dgca(csv_path: Path = DEFAULT_CSV_PATH, dry_run: bool = False) -> dict:
    if not csv_path.exists():
        logger.warning(
            f"DGCA stats file not found at: {csv_path}\n"
            "DGCA data is optional for Phase 1.\n"
            "Download from https://dgca.gov.in/digigov-portal/ and place in data/external/"
        )
        return {"status": "file_not_found", "path": str(csv_path)}

    logger.info(f"Loading DGCA stats from: {csv_path}")
    df = pd.read_csv(csv_path, low_memory=False)
    logger.info(f"Raw shape: {df.shape}")

    cols = {c.lower().strip(): c for c in df.columns}

    records = []
    for _, row in df.iterrows():
        try:
            period = str(row.get(cols.get("period", cols.get("month", "")), "")).strip()
            airline = str(row.get(cols.get("airline", cols.get("carrier", "")), "")).strip() or None
            origin = str(row.get(cols.get("origin", cols.get("from", "")), "")).strip() or None
            destination = str(row.get(cols.get("destination", cols.get("to", "")), "")).strip() or None

            def _int(col_candidates):
                for c in col_candidates:
                    if c in cols:
                        v = row.get(cols[c])
                        if pd.notna(v):
                            try:
                                return int(float(str(v).replace(",", "")))
                            except (ValueError, TypeError):
                                pass
                return None

            def _float(col_candidates):
                for c in col_candidates:
                    if c in cols:
                        v = row.get(cols[c])
                        if pd.notna(v):
                            try:
                                return float(str(v).replace(",", "").replace("%", ""))
                            except (ValueError, TypeError):
                                pass
                return None

            records.append({
                "period": period,
                "airline": airline,
                "origin": origin,
                "destination": destination,
                "passengers": _int(["passengers", "pax", "passenger_count"]),
                "flights_operated": _int(["flights_operated", "flights", "departures"]),
                "seats_offered": _int(["seats_offered", "seats", "capacity"]),
                "load_factor": _float(["load_factor", "plf", "pax_load_factor"]),
            })
        except Exception as exc:
            logger.debug(f"Row error: {exc}")

    logger.info(f"Parsed {len(records)} DGCA records.")

    if not dry_run and records:
        _persist(records)

    return {
        "status": "ok",
        "raw_rows": len(df),
        "records_parsed": len(records),
        "dry_run": dry_run,
    }


def _persist(records: list[dict]) -> None:
    from backend.app.db.base import SessionLocal
    from backend.app.db.models import DGCAAviationStat

    session = SessionLocal()()
    try:
        session.query(DGCAAviationStat).delete()
        batch = [DGCAAviationStat(**r) for r in records]
        for i in range(0, len(batch), 500):
            session.bulk_save_objects(batch[i : i + 500])
            session.commit()
        logger.info(f"DGCA stats persisted: {len(records)} records.")
    except Exception as exc:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = load_dgca(args.path, dry_run=args.dry_run)
    print(result)
