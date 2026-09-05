"""
scripts/run_pipeline.py
------------------------
Full Phase 1 data pipeline orchestrator.

Steps:
  1. Initialise database (create tables, seed reference data)
  2. Load Kaggle dataset (if available)
  3. Load GitHub full_fare.csv (if available)
  4. Load DGCA stats (if available)
  5. Print summary report

Usage:
  python scripts/run_pipeline.py
  python scripts/run_pipeline.py --dry-run    # no DB writes
  python scripts/run_pipeline.py --skip-db    # skip DB init (already done)
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_pipeline(dry_run: bool = False, skip_db: bool = False) -> dict:
    results = {}

    # ── Step 1: DB init ───────────────────────────────────────────────────────
    if not skip_db and not dry_run:
        logger.info("Step 1/4: Initialising database...")
        try:
            from backend.app.db.init_db import init_db
            init_db()
            results["db_init"] = "success"
        except Exception as exc:
            logger.error(f"DB init failed: {exc}")
            results["db_init"] = f"failed: {exc}"
    else:
        logger.info("Step 1/4: Skipping DB init (--skip-db or --dry-run).")
        results["db_init"] = "skipped"

    # ── Step 2: Kaggle ────────────────────────────────────────────────────────
    logger.info("Step 2/4: Loading Kaggle dataset...")
    try:
        from scripts.load_kaggle import load_kaggle
        kaggle_result = load_kaggle(dry_run=dry_run)
        results["kaggle"] = kaggle_result
    except Exception as exc:
        logger.error(f"Kaggle load failed: {exc}")
        results["kaggle"] = {"status": "error", "message": str(exc)}

    # ── Step 3: GitHub fares ──────────────────────────────────────────────────
    logger.info("Step 3/4: Loading GitHub full_fare.csv...")
    try:
        from scripts.load_github_fares import load_github_fares
        github_result = load_github_fares(dry_run=dry_run)
        results["github_fares"] = github_result
    except Exception as exc:
        logger.error(f"GitHub fares load failed: {exc}")
        results["github_fares"] = {"status": "error", "message": str(exc)}

    # ── Step 4: DGCA ──────────────────────────────────────────────────────────
    logger.info("Step 4/4: Loading DGCA stats...")
    try:
        from scripts.load_dgca import load_dgca
        dgca_result = load_dgca(dry_run=dry_run)
        results["dgca"] = dgca_result
    except Exception as exc:
        logger.error(f"DGCA load failed: {exc}")
        results["dgca"] = {"status": "error", "message": str(exc)}

    return results


def print_summary(results: dict) -> None:
    print("\n" + "=" * 60)
    print("  FARECAST — Phase 1 Pipeline Summary")
    print("=" * 60)

    db = results.get("db_init", "unknown")
    print(f"\n  Database Init   : {db}")

    for source_key in ["kaggle", "github_fares", "dgca"]:
        r = results.get(source_key, {})
        status = r.get("status", "unknown")
        if status == "ok":
            print(
                f"\n  {source_key.upper():20s}: {r.get('records_cleaned', 0)} records cleaned "
                f"(from {r.get('raw_rows', 0)} raw rows)"
            )
        elif status == "file_not_found":
            print(f"\n  {source_key.upper():20s}: FILE NOT FOUND — see instructions above")
        else:
            print(f"\n  {source_key.upper():20s}: {status}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full Phase 1 data pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Parse and clean only; no DB writes")
    parser.add_argument("--skip-db", action="store_true", help="Skip DB initialisation step")
    args = parser.parse_args()

    results = run_pipeline(dry_run=args.dry_run, skip_db=args.skip_db)
    print_summary(results)
