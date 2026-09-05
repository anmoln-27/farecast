"""
backend/app/ml/train.py
-----------------------
Training and evaluation engine for Indian Domestic Airfare Prediction.

Steps:
  1. Load & validate historical Kaggle airfare dataset.
  2. Feature engineering & reproducible 80/20 train/test split (seed=42).
  3. Train candidate models (Linear Regression, Random Forest, HistGradientBoosting, CatBoost).
  4. Evaluate on unseen test data (MAE, RMSE, R², MAPE).
  5. Select champion model using lowest test MAE.
  6. Compute empirical prediction uncertainty range from test residuals.
  7. Generate error analysis charts saved to docs/figures/.
  8. Serialize winning model pipeline to models/airfare_model.joblib & metadata.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
import joblib

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.ml.features import (
    ALL_MODEL_FEATURES,
    CATEGORICAL_FEATURES,
    NUMERICAL_FEATURES,
    prepare_features,
)
from backend.app.ml.models import create_model_pipeline, get_candidate_models

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

MODELS_DIR = PROJECT_ROOT / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

FIGURES_DIR = PROJECT_ROOT / "docs" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def calculate_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Absolute Percentage Error on positive fares."""
    mask = y_true > 0
    if not np.any(mask):
        return 0.0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def generate_error_visualizations(
    y_test: np.ndarray,
    y_pred: np.ndarray,
    test_df: pd.DataFrame,
    winning_model_name: str,
) -> dict[str, str]:
    """Generate diagnostic error analysis charts and save to docs/figures/."""
    residuals = y_test - y_pred
    abs_residuals = np.abs(residuals)
    saved_figures = {}

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # 1. Residual Distribution
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(residuals, bins=60, color="#1a4e8a", edgecolor="white", alpha=0.85)
    ax.axvline(0, color="#c44d58", linestyle="--", linewidth=1.5, label="Zero Error")
    ax.axvline(np.median(residuals), color="#f0b429", linestyle=":", linewidth=1.5, label=f"Median ({np.median(residuals):.0f} INR)")
    ax.set_title(f"Residual Distribution — {winning_model_name}", fontsize=12, fontweight="bold")
    ax.set_xlabel("Residual (Actual − Predicted Fare in ₹)")
    ax.set_ylabel("Observation Count")
    ax.legend()
    res_path = FIGURES_DIR / "residual_distribution.png"
    fig.savefig(res_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved_figures["residual_distribution"] = str(res_path)

    # 2. Actual vs Predicted Scatter Plot (sample 5,000 for clarity)
    fig, ax = plt.subplots(figsize=(7, 7))
    sample_idx = np.random.choice(len(y_test), min(5000, len(y_test)), replace=False)
    ax.scatter(y_pred[sample_idx], y_test[sample_idx], alpha=0.2, color="#2e7bcf", s=15, edgecolors="none")
    max_val = max(np.max(y_test[sample_idx]), np.max(y_pred[sample_idx]))
    ax.plot([0, max_val], [0, max_val], color="#c44d58", linestyle="--", linewidth=1.8, label="Perfect Prediction (y = x)")
    ax.set_title(f"Actual vs. Predicted Fares — {winning_model_name}", fontsize=12, fontweight="bold")
    ax.set_xlabel("Predicted Fare (₹)")
    ax.set_ylabel("Actual Fare (₹)")
    ax.legend()
    scatter_path = FIGURES_DIR / "actual_vs_predicted.png"
    fig.savefig(scatter_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved_figures["actual_vs_predicted"] = str(scatter_path)

    # 3. Error by Airline
    fig, ax = plt.subplots(figsize=(8, 4.5))
    test_df_copy = test_df.copy()
    test_df_copy["abs_error"] = abs_residuals
    airline_mae = test_df_copy.groupby("airline")["abs_error"].mean().sort_values(ascending=False)
    airline_mae.plot(kind="bar", ax=ax, color="#4ca3dd", edgecolor="#1a4e8a")
    ax.set_title(f"Mean Absolute Error by Airline — {winning_model_name}", fontsize=11, fontweight="bold")
    ax.set_ylabel("MAE (₹)")
    ax.set_xlabel("Airline")
    plt.xticks(rotation=30, ha="right")
    airline_path = FIGURES_DIR / "error_by_airline.png"
    fig.savefig(airline_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved_figures["error_by_airline"] = str(airline_path)

    # 4. Error by Cabin Class
    fig, ax = plt.subplots(figsize=(5, 4))
    class_mae = test_df_copy.groupby("cabin_class")["abs_error"].mean()
    class_mae.plot(kind="bar", ax=ax, color=["#e07b39", "#2d9e6b"], edgecolor="#333333")
    ax.set_title("MAE by Cabin Class", fontsize=11, fontweight="bold")
    ax.set_ylabel("MAE (₹)")
    ax.set_xlabel("Cabin Class")
    plt.xticks(rotation=0)
    cabin_path = FIGURES_DIR / "error_by_cabin.png"
    fig.savefig(cabin_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved_figures["error_by_cabin"] = str(cabin_path)

    logger.info(f"Diagnostic figures saved to {FIGURES_DIR}")
    return saved_figures


def run_training_pipeline(
    data_path: Path = PROJECT_ROOT / "data" / "raw" / "Clean_Dataset.csv",
    random_state: int = 42,
) -> dict:
    """Run full Phase 2 training, benchmarking, evaluation, and artifact export."""
    logger.info("=" * 60)
    logger.info("  FARECAST — Phase 2 Machine Learning Training Pipeline")
    logger.info("=" * 60)

    if not data_path.exists():
        raise FileNotFoundError(f"Training dataset not found at: {data_path}")

    logger.info(f"Loading dataset from: {data_path}")
    raw_df = pd.read_csv(data_path)
    logger.info(f"Loaded raw records: {len(raw_df):,} rows × {len(raw_df.columns)} columns")

    # Step 1: Feature Engineering
    logger.info("Executing feature engineering and schema standardization...")
    X, y = prepare_features(raw_df, is_training=True)
    if y is None:
        raise ValueError("Target column 'price' / 'fare' not found in dataset.")

    # Remove rows with null targets or impossible fares if any
    valid_mask = y.notna() & (y >= 500) & (y <= 200000)
    X = X[valid_mask].reset_index(drop=True)
    y = y[valid_mask].reset_index(drop=True)
    logger.info(f"Valid training observations after validation: {len(X):,}")

    # Step 2: Train/Test Split (80/20, seed=42)
    # The dataset provides booking snapshots across days_left rather than absolute timestamps.
    # A stratified-by-cabin random split ensures balanced coverage of economy and business fares.
    logger.info("Splitting dataset: 80% train / 20% test (seed=42, stratified by cabin_class)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=random_state,
        stratify=X["cabin_class"],
    )
    logger.info(f"Training set: {len(X_train):,} | Test set: {len(X_test):,}")

    # Step 3: Candidate Models Training & Evaluation
    candidate_models = get_candidate_models(random_state=random_state)
    results: dict[str, dict[str, Any]] = {}
    trained_pipelines: dict[str, Any] = {}
    test_predictions: dict[str, np.ndarray] = {}

    print("\n" + "=" * 65)
    print(f"{'Model':24s} | {'MAE (INR)':10s} | {'RMSE (INR)':10s} | {'R2':8s} | {'MAPE (%)':8s}")
    print("-" * 65)

    for model_name, model_estimator in candidate_models.items():
        logger.info(f"Training {model_name}...")
        pipeline = create_model_pipeline(model_estimator)
        pipeline.fit(X_train, y_train)
        trained_pipelines[model_name] = pipeline

        # Evaluate on unseen test data
        y_pred = pipeline.predict(X_test)
        test_predictions[model_name] = y_pred

        mae = mean_absolute_error(y_test, y_pred)
        rmse = root_mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        mape = calculate_mape(y_test.values, y_pred)

        results[model_name] = {
            "MAE": round(float(mae), 2),
            "RMSE": round(float(rmse), 2),
            "R2": round(float(r2), 4),
            "MAPE": round(float(mape), 2),
        }

        print(f"{model_name:24s} | {mae:10.2f} | {rmse:10.2f} | {r2:8.4f} | {mape:8.2f}%")

    print("=" * 65 + "\n")

    # Step 4: Model Selection (Lowest Test MAE)
    best_model_name = min(results.keys(), key=lambda m: results[m]["MAE"])
    best_pipeline = trained_pipelines[best_model_name]
    best_metrics = results[best_model_name]
    best_predictions = test_predictions[best_model_name]

    logger.info(
        f"Champion Model Selected: '{best_model_name}' "
        f"(MAE: ₹{best_metrics['MAE']:.2f}, RMSE: ₹{best_metrics['RMSE']:.2f}, R²: {best_metrics['R2']:.4f})"
    )

    # Step 5: Prediction Range Calculation (Empirical 80th percentile residual margin)
    residuals = y_test.values - best_predictions
    abs_residuals = np.abs(residuals)
    residual_margin_80 = float(np.percentile(abs_residuals, 80))
    logger.info(f"Empirical 80th-percentile residual margin: ±₹{residual_margin_80:.2f}")

    # Step 6: Visualizations & Diagnostics
    figure_paths = generate_error_visualizations(
        y_test=y_test.values,
        y_pred=best_predictions,
        test_df=X_test,
        winning_model_name=best_model_name,
    )

    # Step 7: Save Winning Pipeline
    model_save_path = MODELS_DIR / "airfare_model.joblib"
    joblib.dump(best_pipeline, model_save_path)
    logger.info(f"Saved champion pipeline to: {model_save_path}")

    # Step 8: Save Comprehensive Metadata
    metadata = {
        "model_name": best_model_name,
        "training_timestamp": datetime.now().isoformat(),
        "dataset_source": "Kaggle Flight Price Prediction (Shubham Bathwal)",
        "dataset_path": str(data_path),
        "total_records": len(X),
        "train_records": len(X_train),
        "test_records": len(X_test),
        "target_variable": "fare_inr",
        "features": {
            "categorical": CATEGORICAL_FEATURES,
            "numerical": NUMERICAL_FEATURES,
            "all": ALL_MODEL_FEATURES,
        },
        "all_model_benchmarks": results,
        "champion_metrics": best_metrics,
        "prediction_range": {
            "methodology": "80th percentile of absolute test residuals",
            "residual_margin_inr": round(residual_margin_80, 2),
            "interpretation": (
                f"In 80% of unseen historical test observations, the actual airfare was within "
                f"±₹{residual_margin_80:.0f} of the model prediction."
            ),
        },
        "figures": figure_paths,
    }

    metadata_path = MODELS_DIR / "model_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Saved metadata to: {metadata_path}")

    return {
        "status": "success",
        "champion_model": best_model_name,
        "champion_metrics": best_metrics,
        "benchmarks": results,
        "model_path": str(model_save_path),
        "metadata_path": str(metadata_path),
        "residual_margin_80": residual_margin_80,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train airfare prediction models")
    parser.add_argument("--data", type=str, default=str(PROJECT_ROOT / "data" / "raw" / "Clean_Dataset.csv"))
    args = parser.parse_args()
    run_training_pipeline(data_path=Path(args.data))
