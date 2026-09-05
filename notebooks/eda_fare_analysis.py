"""
notebooks/eda_fare_analysis.py
-------------------------------
EDA script (runnable as plain Python or convertible to Jupyter notebook).

Analyses:
  1. Dataset dimensions
  2. Missing values
  3. Duplicate records
  4. Airline distribution
  5. Route distribution
  6. Class distribution
  7. Fare distribution (histogram + boxplot)
  8. Fare by airline (boxplot)
  9. Fare by route (top-20 routes)
  10. Fare vs Days Left (scatter/bin plot)
  11. Fare vs Stops
  12. Fare vs Duration
  13. Temporal patterns (if travel_date available)

Charts saved to: docs/figures/

Usage:
  python notebooks/eda_fare_analysis.py
  python notebooks/eda_fare_analysis.py --source github_full_fare
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for script mode

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

FIGURES_DIR = PROJECT_ROOT / "docs" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

PALETTE = [
    "#1a4e8a", "#2e7bcf", "#4ca3dd", "#a8d1f0",
    "#e07b39", "#f0b429", "#2d9e6b", "#c44d58",
]

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "#f8f9fa",
    "axes.edgecolor": "#cccccc",
    "axes.labelcolor": "#333333",
    "xtick.color": "#555555",
    "ytick.color": "#555555",
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
})


def _save(fig, name: str) -> None:
    path = FIGURES_DIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Saved: {path}")


def load_data(source: str) -> pd.DataFrame | None:
    """Load data from CSV file (Kaggle or GitHub)."""
    if source == "kaggle":
        csv_path = PROJECT_ROOT / "data" / "raw" / "Clean_Dataset.csv"
    elif source == "github_full_fare":
        csv_path = PROJECT_ROOT / "data" / "raw" / "full_fare.csv"
    else:
        logger.error(f"Unknown source: {source}")
        return None

    if not csv_path.exists():
        logger.warning(f"Data file not found: {csv_path}")
        return None

    df = pd.read_csv(csv_path, low_memory=False)
    logger.info(f"Loaded {source}: {df.shape[0]:,} rows × {df.shape[1]} columns")
    return df


def normalise_kaggle(df: pd.DataFrame) -> pd.DataFrame:
    """Standardise Kaggle column names."""
    rename = {
        "Airline": "airline",
        "Flight": "flight_number",
        "Source City": "origin",
        "Departure Time": "departure_time",
        "Stops": "stops",
        "Arrival Time": "arrival_time",
        "Destination City": "destination",
        "Class": "cabin_class",
        "Duration": "duration_hours",
        "Days Left": "days_left",
        "Price": "fare",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    if "duration_hours" in df.columns:
        df["duration_minutes"] = pd.to_numeric(df["duration_hours"], errors="coerce") * 60
    return df


def run_eda(source: str = "kaggle") -> None:
    df = load_data(source)
    if df is None:
        logger.warning(f"No data for source '{source}' — skipping EDA.")
        return

    if source == "kaggle":
        df = normalise_kaggle(df)

    # ── 1. Dataset dimensions ─────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  EDA: {source.upper()}")
    print(f"{'='*60}")
    print(f"  Rows    : {len(df):,}")
    print(f"  Columns : {len(df.columns)}")
    print(f"\n  Columns:\n  {list(df.columns)}\n")

    # ── 2. Missing values ─────────────────────────────────────────────────────
    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(2)
    missing_df = pd.DataFrame({"missing_count": missing, "missing_pct": missing_pct})
    missing_df = missing_df[missing_df["missing_count"] > 0].sort_values("missing_pct", ascending=False)
    print("  Missing Values:")
    if missing_df.empty:
        print("  → No missing values detected.")
    else:
        print(missing_df.to_string())
    print()

    # ── 3. Duplicates ─────────────────────────────────────────────────────────
    dupes = df.duplicated().sum()
    print(f"  Duplicate rows: {dupes:,} ({dupes/len(df)*100:.2f}%)\n")

    # Detect fare column
    fare_col = "fare" if "fare" in df.columns else None
    if fare_col is None:
        for c in df.columns:
            if "price" in c.lower() or "fare" in c.lower():
                fare_col = c
                break

    if fare_col is None:
        logger.warning("No fare/price column found — skipping fare-related plots.")
        return

    df[fare_col] = pd.to_numeric(df[fare_col], errors="coerce")
    df_valid = df.dropna(subset=[fare_col])
    df_valid = df_valid[(df_valid[fare_col] >= 500) & (df_valid[fare_col] <= 200_000)]

    print(f"  Fare statistics (after cleaning: ≥500, ≤200,000 INR):")
    print(f"  {df_valid[fare_col].describe().round(2)}\n")

    airline_col = "airline" if "airline" in df_valid.columns else None
    route_col = None
    if "origin" in df_valid.columns and "destination" in df_valid.columns:
        df_valid = df_valid.copy()
        df_valid["route"] = df_valid["origin"].astype(str) + "–" + df_valid["destination"].astype(str)
        route_col = "route"

    cabin_col = "cabin_class" if "cabin_class" in df_valid.columns else None
    days_col = "days_left" if "days_left" in df_valid.columns else None
    stops_col = "stops" if "stops" in df_valid.columns else None
    dur_col = "duration_minutes" if "duration_minutes" in df_valid.columns else None

    # ── 4. Airline distribution ───────────────────────────────────────────────
    if airline_col:
        airline_counts = df_valid[airline_col].value_counts()
        fig, ax = plt.subplots(figsize=(10, 5))
        bars = ax.bar(airline_counts.index, airline_counts.values, color=PALETTE[0], edgecolor="white")
        ax.set_title(f"Airline Distribution ({source})")
        ax.set_xlabel("Airline")
        ax.set_ylabel("Number of Observations")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        _save(fig, f"{source}_airline_distribution.png")

    # ── 5. Route distribution (top 20) ────────────────────────────────────────
    if route_col:
        top_routes = df_valid[route_col].value_counts().head(20)
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.barh(top_routes.index[::-1], top_routes.values[::-1], color=PALETTE[1])
        ax.set_title(f"Top 20 Routes by Observation Count ({source})")
        ax.set_xlabel("Number of Observations")
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
        plt.tight_layout()
        _save(fig, f"{source}_route_distribution.png")

    # ── 6. Class distribution ─────────────────────────────────────────────────
    if cabin_col:
        class_counts = df_valid[cabin_col].value_counts()
        fig, ax = plt.subplots(figsize=(7, 4))
        wedges, texts, autotexts = ax.pie(
            class_counts.values,
            labels=class_counts.index,
            autopct="%1.1f%%",
            colors=PALETTE[:len(class_counts)],
            startangle=140,
        )
        ax.set_title(f"Cabin Class Distribution ({source})")
        _save(fig, f"{source}_class_distribution.png")

    # ── 7. Fare distribution ──────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].hist(df_valid[fare_col], bins=60, color=PALETTE[0], edgecolor="white")
    axes[0].set_title("Fare Distribution (Histogram)")
    axes[0].set_xlabel("Fare (INR)")
    axes[0].set_ylabel("Count")
    axes[0].xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x:,.0f}"))

    axes[1].boxplot(df_valid[fare_col].dropna(), patch_artist=True,
                    boxprops=dict(facecolor=PALETTE[3]),
                    medianprops=dict(color="#e07b39", linewidth=2))
    axes[1].set_title("Fare Distribution (Boxplot)")
    axes[1].set_ylabel("Fare (INR)")
    axes[1].yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x:,.0f}"))
    plt.suptitle(f"Fare Distribution — {source}", fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()
    _save(fig, f"{source}_fare_distribution.png")

    # ── 8. Fare by airline ────────────────────────────────────────────────────
    if airline_col:
        airline_data = [
            df_valid[df_valid[airline_col] == a][fare_col].dropna().values
            for a in df_valid[airline_col].unique()
            if len(df_valid[df_valid[airline_col] == a]) >= 10
        ]
        airline_labels = [
            a for a in df_valid[airline_col].unique()
            if len(df_valid[df_valid[airline_col] == a]) >= 10
        ]
        if airline_data:
            fig, ax = plt.subplots(figsize=(13, 6))
            bp = ax.boxplot(airline_data, patch_artist=True, labels=airline_labels)
            for patch, color in zip(bp["boxes"], PALETTE * 5):
                patch.set_facecolor(color)
                patch.set_alpha(0.8)
            for median in bp["medians"]:
                median.set(color="#333333", linewidth=2)
            ax.set_title(f"Fare by Airline ({source})")
            ax.set_xlabel("Airline")
            ax.set_ylabel("Fare (INR)")
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x:,.0f}"))
            plt.xticks(rotation=30, ha="right")
            plt.tight_layout()
            _save(fig, f"{source}_fare_by_airline.png")

    # ── 9. Fare by route (top 15) ─────────────────────────────────────────────
    if route_col:
        top_routes_list = df_valid[route_col].value_counts().head(15).index.tolist()
        df_top = df_valid[df_valid[route_col].isin(top_routes_list)]
        route_medians = df_top.groupby(route_col)[fare_col].median().sort_values(ascending=False)

        fig, ax = plt.subplots(figsize=(13, 6))
        ax.bar(route_medians.index, route_medians.values, color=PALETTE[2], edgecolor="white")
        ax.set_title(f"Median Fare by Route — Top 15 Routes ({source})")
        ax.set_xlabel("Route")
        ax.set_ylabel("Median Fare (INR)")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x:,.0f}"))
        plt.xticks(rotation=40, ha="right")
        plt.tight_layout()
        _save(fig, f"{source}_fare_by_route.png")

    # ── 10. Fare vs Days Left ─────────────────────────────────────────────────
    if days_col and df_valid[days_col].notna().sum() > 100:
        df_dl = df_valid[[days_col, fare_col]].dropna()
        bins = list(range(0, 50, 5)) + [60, 75, 90, 120, 180, 365]
        df_dl["days_bin"] = pd.cut(df_dl[days_col], bins=bins)
        bin_means = df_dl.groupby("days_bin", observed=True)[fare_col].mean().dropna()

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(
            range(len(bin_means)), bin_means.values,
            marker="o", color=PALETTE[0], linewidth=2, markersize=6
        )
        ax.set_xticks(range(len(bin_means)))
        ax.set_xticklabels([str(i) for i in bin_means.index], rotation=45, ha="right", fontsize=8)
        ax.set_title(f"Average Fare vs Days Left to Departure ({source})")
        ax.set_xlabel("Days Left Bucket")
        ax.set_ylabel("Average Fare (INR)")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x:,.0f}"))
        ax.grid(axis="y", alpha=0.3)
        plt.tight_layout()
        _save(fig, f"{source}_fare_vs_days_left.png")

    # ── 11. Fare vs Stops ─────────────────────────────────────────────────────
    if stops_col:
        stops_data = df_valid.groupby(stops_col)[fare_col].median().reset_index()
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar(stops_data[stops_col].astype(str), stops_data[fare_col], color=PALETTE[4], edgecolor="white")
        ax.set_title(f"Median Fare vs Number of Stops ({source})")
        ax.set_xlabel("Stops")
        ax.set_ylabel("Median Fare (INR)")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x:,.0f}"))
        plt.tight_layout()
        _save(fig, f"{source}_fare_vs_stops.png")

    # ── 12. Fare vs Duration ──────────────────────────────────────────────────
    if dur_col and df_valid[dur_col].notna().sum() > 100:
        df_dur = df_valid[[dur_col, fare_col]].dropna()
        df_dur = df_dur[(df_dur[dur_col] > 0) & (df_dur[dur_col] < 1200)]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.scatter(df_dur[dur_col], df_dur[fare_col], alpha=0.2, s=5, color=PALETTE[1])
        # Trend line
        z = np.polyfit(df_dur[dur_col], df_dur[fare_col], 1)
        p = np.poly1d(z)
        x_line = np.linspace(df_dur[dur_col].min(), df_dur[dur_col].max(), 100)
        ax.plot(x_line, p(x_line), color=PALETTE[4], linewidth=2, label="Trend")
        ax.set_title(f"Fare vs Flight Duration ({source})")
        ax.set_xlabel("Duration (minutes)")
        ax.set_ylabel("Fare (INR)")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x:,.0f}"))
        ax.legend()
        plt.tight_layout()
        _save(fig, f"{source}_fare_vs_duration.png")

    # ── 13. Temporal patterns ─────────────────────────────────────────────────
    if "travel_date" in df_valid.columns:
        try:
            df_valid = df_valid.copy()
            df_valid["travel_date"] = pd.to_datetime(df_valid["travel_date"], errors="coerce")
            df_dated = df_valid.dropna(subset=["travel_date"])
            if len(df_dated) > 100:
                df_dated["month"] = df_dated["travel_date"].dt.to_period("M")
                monthly = df_dated.groupby("month")[fare_col].mean()
                fig, ax = plt.subplots(figsize=(13, 5))
                ax.plot(monthly.index.astype(str), monthly.values, marker="o",
                        color=PALETTE[0], linewidth=2)
                ax.set_title(f"Average Fare by Month ({source})")
                ax.set_xlabel("Month")
                ax.set_ylabel("Average Fare (INR)")
                ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x:,.0f}"))
                plt.xticks(rotation=45, ha="right")
                ax.grid(axis="y", alpha=0.3)
                plt.tight_layout()
                _save(fig, f"{source}_temporal_trend.png")
        except Exception as exc:
            logger.warning(f"Temporal plot failed: {exc}")

    print(f"\n  EDA complete. Charts saved to: {FIGURES_DIR}")
    print("  Available figures:")
    for f in sorted(FIGURES_DIR.glob(f"{source}_*.png")):
        print(f"    {f.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["kaggle", "github_full_fare", "all"], default="kaggle")
    args = parser.parse_args()

    if args.source == "all":
        for src in ["kaggle", "github_full_fare"]:
            run_eda(src)
    else:
        run_eda(args.source)
