"""
backend/app/ml/predictor.py
---------------------------
Reusable airfare prediction service for REST API and programmatic inference.

Loads the champion serialized pipeline, validates input flight parameters,
and generates bounded fare predictions with empirical uncertainty ranges.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from backend.app.ml.features import prepare_features

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent.parent.parent / "models" / "airfare_model.joblib"
DEFAULT_METADATA_PATH = Path(__file__).resolve().parent.parent.parent.parent / "models" / "model_metadata.json"


class ModelNotLoadedError(RuntimeError):
    """Raised when prediction is attempted without an available trained model artifact."""
    pass


class InvalidInputError(ValueError):
    """Raised when flight parameters fail validation."""
    pass


class FarePredictor:
    """Production predictor wrapping the scikit-learn champion pipeline."""

    def __init__(
        self,
        model_path: Path | str = DEFAULT_MODEL_PATH,
        metadata_path: Path | str = DEFAULT_METADATA_PATH,
    ):
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path)
        self._pipeline: Any | None = None
        self._metadata: dict[str, Any] | None = None
        self._residual_margin: float = 2500.0  # Fallback margin in ₹

    def load(self) -> None:
        """Load the model pipeline and associated metadata from disk."""
        if not self.model_path.exists():
            raise ModelNotLoadedError(
                f"Model artifact not found at '{self.model_path}'. "
                "Please run 'python -m backend.app.ml.train' first."
            )

        logger.info(f"Loading airfare prediction model from {self.model_path}")
        self._pipeline = joblib.load(self.model_path)

        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self._metadata = json.load(f)
                range_info = self._metadata.get("prediction_range", {})
                self._residual_margin = float(range_info.get("residual_margin_inr", 2500.0))
            except Exception as exc:
                logger.warning(f"Could not read metadata: {exc}. Using fallback residual margin.")
        else:
            self._metadata = {"model_name": "Trained Pipeline"}

    @property
    def is_loaded(self) -> bool:
        return self._pipeline is not None

    def get_metadata(self) -> dict[str, Any]:
        """Return metadata of the loaded model."""
        if not self.is_loaded:
            self.load()
        return self._metadata or {}

    def predict_fare(self, flight_details: dict[str, Any]) -> dict[str, Any]:
        """
        Predict fare for a single flight option.

        Expected flight_details keys:
          - origin / source_city (required): e.g. "Delhi" or "DEL"
          - destination / destination_city (required): e.g. "Mumbai" or "BOM"
          - airline (optional, default="IndiGo"): e.g. "Air India", "Vistara", "SpiceJet"
          - cabin_class (optional, default="Economy"): "Economy" or "Business"
          - departure_time (optional, default="Morning"): "Early Morning", "Morning", "Afternoon", "Evening", "Night", "Late Night"
          - arrival_time (optional, default="Afternoon"): same categories
          - stops (optional, default=0): 0, 1, or 2
          - duration_minutes / duration (optional, default=130): flight duration in minutes or hours
          - days_left (optional, default=20): days remaining before departure (1 - 49)

        Returns:
          {
              "predicted_fare": float,
              "lower_estimate": float,
              "upper_estimate": float,
              "currency": "INR",
              "model": str,
              "data_basis": str,
              "route": str,
              "airline": str,
              "cabin_class": str,
              "days_left": int,
              "prediction_uncertainty_margin": float
          }
        """
        if not self.is_loaded:
            self.load()

        # Input validation
        origin = flight_details.get("origin") or flight_details.get("source_city")
        destination = flight_details.get("destination") or flight_details.get("destination_city")

        if not origin or not destination:
            raise InvalidInputError("Both origin (source_city) and destination (destination_city) are required.")

        origin_str = str(origin).strip()
        dest_str = str(destination).strip()

        if origin_str.lower() == dest_str.lower():
            raise InvalidInputError("Origin and destination cities cannot be identical.")

        # Construct single-row DataFrame
        df_input = pd.DataFrame([flight_details])

        # Preprocess features using common feature pipeline
        X, _ = prepare_features(df_input, is_training=False)

        # Predict
        pred = float(self._pipeline.predict(X)[0])
        predicted_fare = max(800.0, round(pred, 2))

        # Compute empirical prediction range
        lower_estimate = max(500.0, round(predicted_fare - self._residual_margin, 2))
        upper_estimate = round(predicted_fare + self._residual_margin, 2)

        model_name = self._metadata.get("model_name", "Trained Airfare Model") if self._metadata else "Trained Airfare Model"

        return {
            "predicted_fare": round(predicted_fare, 2),
            "lower_estimate": round(lower_estimate, 2),
            "upper_estimate": round(upper_estimate, 2),
            "currency": "INR",
            "model": model_name,
            "data_basis": "Historical airfare patterns (Kaggle Indian Domestic dataset)",
            "route": f"{X['source_city'].iloc[0]}_{X['destination_city'].iloc[0]}",
            "airline": str(X["airline"].iloc[0]),
            "cabin_class": str(X["cabin_class"].iloc[0]),
            "days_left": int(X["days_left"].iloc[0]),
            "prediction_uncertainty_margin": round(self._residual_margin, 2),
        }

    def predict_batch(self, flights: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run predictions for multiple flight options efficiently."""
        if not flights:
            return []
        return [self.predict_fare(item) for item in flights]


# Singleton instance for API endpoints
_global_predictor: FarePredictor | None = None


def get_predictor() -> FarePredictor:
    """Return singleton FarePredictor instance."""
    global _global_predictor
    if _global_predictor is None:
        _global_predictor = FarePredictor()
    return _global_predictor
