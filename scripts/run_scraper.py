"""
scripts/run_scraper.py
----------------------
CLI tool to execute multi-source airline scrapers across Indian domestic routes
and the 5 mandatory advance-purchase windows (T+1, T+7, T+15, T+30, T+45).

Usage:
    python scripts/run_scraper.py --simulate
    python scripts/run_scraper.py --live --no-save
"""
import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.scrapers.orchestrator import ScraperOrchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Multi-Source Airfare Scraper Ingestion Sweep.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Attempt live HTTP scraping against airline websites.",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        default=True,
        help="Use high-fidelity deterministic simulation (default).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not persist scraped fares to the database.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    simulate = not args.live
    save_to_db = not args.no_save

    print("=" * 70)
    print("  FARECAST: Multi-Source Airfare Scraping & Ingestion Sweep")
    print("=" * 70)
    print(f"Mode: {'HIGH-FIDELITY SIMULATION' if simulate else 'LIVE HTTP SCRAPING'}")
    print(f"Database Persistence: {'ENABLED' if save_to_db else 'DISABLED'}")
    print("Windows: T+1, T+7, T+15, T+30, T+45")
    print("-" * 70)

    orchestrator = ScraperOrchestrator()
    result = orchestrator.run_sweep(simulate=simulate, save_to_db=save_to_db)

    print("\n" + "=" * 70)
    print("  SWEEP SUMMARY")
    print("=" * 70)
    print(f"Routes Swept:       {result['routes_swept']}")
    print(f"Windows Swept:      {', '.join(result['windows_swept'])}")
    print(f"Raw Quotes:         {result['raw_count']}")
    print(f"Cleaned Fares:      {result['cleaned_count']}")
    print(f"Persisted to DB:    {result['saved_count']}")
    print(f"Cleaning Log:       {result['cleaning_report']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
