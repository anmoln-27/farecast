"""
backend/app/ml/models.py
------------------------
Model definitions and pipeline construction for airfare regression.
Defines baseline, ensemble, and gradient boosting candidate models.
"""
from __future__ import annotations

import logging
from typing import Any
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline

from backend.app.ml.features import build_preprocessor

logger = logging.getLogger(__name__)


def get_candidate_models(random_state: int = 42) -> dict[str, Any]:
    """
    Return dictionary of model candidates to evaluate.
    
    Includes:
      1. Linear Regression (baseline)
      2. Random Forest Regressor
      3. HistGradientBoostingRegressor
      4. CatBoost Regressor (if available)
    """
    models: dict[str, Any] = {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(
            n_estimators=100,
            max_depth=16,
            min_samples_split=5,
            random_state=random_state,
            n_jobs=-1,
        ),
        "HistGradientBoosting": HistGradientBoostingRegressor(
            max_iter=150,
            max_depth=10,
            learning_rate=0.1,
            random_state=random_state,
        ),
    }

    # Try importing CatBoost
    try:
        from catboost import CatBoostRegressor
        models["CatBoost"] = CatBoostRegressor(
            iterations=250,
            depth=6,
            learning_rate=0.1,
            random_seed=random_state,
            verbose=0,
        )
        logger.info("CatBoost Regressor loaded successfully.")
    except ImportError:
        logger.info("CatBoost not installed. Proceeding with standard scikit-learn models.")
    except Exception as exc:
        logger.warning(f"Could not initialize CatBoost: {exc}")

    return models


def create_model_pipeline(model_instance: Any) -> Pipeline:
    """Wrap preprocessor and regressor into a unified scikit-learn Pipeline."""
    preprocessor = build_preprocessor()
    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("regressor", model_instance),
        ]
    )
