"""
backend/app/ml
--------------
Machine Learning package for airfare prediction.
"""
from backend.app.ml.features import prepare_features, build_preprocessor
from backend.app.ml.models import get_candidate_models, create_model_pipeline
from backend.app.ml.predictor import FarePredictor, get_predictor

__all__ = [
    "prepare_features",
    "build_preprocessor",
    "get_candidate_models",
    "create_model_pipeline",
    "FarePredictor",
    "get_predictor",
]
