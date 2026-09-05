"""
scripts/clean_fares.py
-----------------------
Standalone cleaning script. Reads processed/raw fare parquet or CSV,
applies the cleaner pipeline, writes to data/processed/.

Usage:
  python scripts/clean_fares.py --source kaggle
  python scripts/clean_fares.py --source github_full_fare
  python scripts/clean_fares.py --source all
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


def clean_source(source: str) -> dict:
    if source == "kaggle":
        from scripts.load_kaggle import load_kaggle
        return load_kaggle(dry_run=True)  # Dry run = just clean, no DB write
    elif source == "github_full_fare":
        from scripts.load_github_fares import load_github_fares
        return load_github_fares(dry_run=True)
    else:
        return {"status": "unknown_source"}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["kaggle", "github_full_fare", "all"], default="all")
    args = parser.parse_args()

    if args.source == "all":
        for src in ["kaggle", "github_full_fare"]:
            result = clean_source(src)
            print(f"\n[{src}] {result}")
    else:
        result = clean_source(args.source)
        print(result)
