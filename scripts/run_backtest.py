"""
scripts/run_backtest.py
-----------------------
CLI runner for the 30-Day DGCA Backtesting & Statistical Validation Suite.
Compares Real-Time APIx against official DGCA benchmark series.

Usage:
    python scripts/run_backtest.py
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.analytics.backtest import run_30day_backtest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run 30-day DGCA APIx Backtesting Validation Suite.")
    parser.add_argument(
        "--export-json",
        type=str,
        default="",
        help="Optional path to export backtest results JSON.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("=" * 80)
    print("  FARECAST: 30-DAY AIRFARE PRICE INDEX (APIx) BACKTESTING SUITE")
    print("  Synthetic Benchmark Simulation — Methodology Demonstration")
    print("  [Notice: DGCA fare validation dataset not available in connected public sources]")
    print("=" * 80)

    result = run_30day_backtest()
    if result.get("status") != "success":
        print(f"Backtest Failed: {result.get('message')}")
        sys.exit(1)

    metrics = result["metrics"]
    print("\n[ STATISTICAL VALIDATION METRICS ]")
    print("-" * 50)
    print(f"Pearson Correlation (r):       {metrics['pearson_correlation']:.4f}  (Target: >= 0.8500)")
    print(f"Mean Abs. % Error (MAPE):      {metrics['mape_percent']:.2f}%     (Target: <= 8.00%)")
    print(f"Directional Accuracy:          {metrics['directional_accuracy_percent']:.1f}%    (Target: >= 80.0%)")
    print(f"Tracking Error Spread:         {metrics['tracking_error']:.4f}")
    print(f"Volatility Ratio (APIx/DGCA):  {metrics['volatility_ratio']:.3f}")
    print(f"Validation Status:             {result['validation_status']}")
    print("-" * 50)

    print("\n[ RECENT 10-DAY COMPARISON SAMPLE ]")
    print(f"{'Date':<12} | {'DGCA Fare':<12} | {'APIx Fare':<12} | {'Error %':<10} | {'DGCA Idx':<10} | {'APIx Idx':<10}")
    print("-" * 75)
    for pt in result["daily_comparison"][-10:]:
        print(
            f"{pt['date']:<12} | "
            f"INR {pt['dgca_fare_inr']:<8.0f} | "
            f"INR {pt['apix_fare_inr']:<8.0f} | "
            f"{pt['percentage_error']:>6.2f}%    | "
            f"{pt['dgca_index']:>8.2f}   | "
            f"{pt['apix_index']:>8.2f}"
        )
    print("=" * 80)
    print("Conclusion: Demonstrates mathematical evaluation framework using a synthetic")
    print("benchmark. Official DGCA route fare validation dataset not available in public sources.")
    print("=" * 80)

    if args.export_json:
        out_path = Path(args.export_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Exported results to: {out_path}")


if __name__ == "__main__":
    main()
