"""
tests/test_ml.py
----------------
Comprehensive test suite for Phase 2 Machine Learning pipeline.

Covers:
  - Feature engineering & schema harmonization
  - Handling of unseen categorical values
  - Model pipeline construction
  - Predictor input validation & error handling
  - Prediction output schema & empirical bound consistency
  - Metadata serialization and loading
"""
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.ml.features import (
    ALL_MODEL_FEATURES,
    CATEGORICAL_FEATURES,
    NUMERICAL_FEATURES,
    build_preprocessor,
    categorize_booking_window,
    is_peak_departure_time,
    prepare_features,
)
from backend.app.ml.predictor import (
    FarePredictor,
    InvalidInputError,
    ModelNotLoadedError,
    get_predictor,
)


class TestFeatureEngineering:
    def test_booking_window_buckets(self):
        assert categorize_booking_window(1) == "last_minute"
        assert categorize_booking_window(3) == "last_minute"
        assert categorize_booking_window(4) == "short_advance"
        assert categorize_booking_window(7) == "short_advance"
        assert categorize_booking_window(15) == "standard"
        assert categorize_booking_window(30) == "early_bird"
        assert categorize_booking_window(None) == "standard"

    def test_peak_departure_window(self):
        assert is_peak_departure_time("Morning") == 1
        assert is_peak_departure_time("Evening") == 1
        assert is_peak_departure_time("morning") == 1
        assert is_peak_departure_time("Night") == 0
        assert is_peak_departure_time("Afternoon") == 0
        assert is_peak_departure_time(None) == 0

    def test_prepare_features_schema_harmony(self):
        # Raw Kaggle-style columns
        df_raw = pd.DataFrame([
            {
                "Airline": "SpiceJet",
                "Flight": "SG-8709",
                "Source City": "Delhi",
                "Departure Time": "Evening",
                "Stops": "zero",
                "Arrival Time": "Night",
                "Destination City": "Mumbai",
                "Class": "Economy",
                "Duration": 2.17,
                "Days Left": 1,
                "Price": 5953,
            }
        ])
        X, y = prepare_features(df_raw, is_training=True)

        assert list(X.columns) == ALL_MODEL_FEATURES
        assert X["airline"].iloc[0] == "SpiceJet"
        assert X["source_city"].iloc[0] == "DEL"
        assert X["destination_city"].iloc[0] == "BOM"
        assert X["route"].iloc[0] == "DEL_BOM"
        assert X["cabin_class"].iloc[0] == "Economy"
        assert X["stops"].iloc[0] == 0
        assert round(X["duration_minutes"].iloc[0], 1) == 130.2
        assert X["days_left"].iloc[0] == 1
        assert X["booking_window"].iloc[0] == "last_minute"
        assert X["is_peak_departure"].iloc[0] == 1
        assert y is not None
        assert y.iloc[0] == 5953

    def test_unseen_categoricals_handling(self):
        """Verify preprocessor handles unseen airlines/cities without failing."""
        preprocessor = build_preprocessor()

        train_data = pd.DataFrame([
            {
                "airline": "IndiGo",
                "source_city": "DEL",
                "destination_city": "BOM",
                "route": "DEL_BOM",
                "departure_time": "Morning",
                "arrival_time": "Afternoon",
                "cabin_class": "Economy",
                "booking_window": "standard",
                "stops": 0,
                "duration_minutes": 130.0,
                "days_left": 20,
                "is_peak_departure": 1,
            }
        ])
        preprocessor.fit(train_data[ALL_MODEL_FEATURES])

        # Test data with completely unseen categorical values
        unseen_data = pd.DataFrame([
            {
                "airline": "BrandNewAirlines",
                "source_city": "PAT",
                "destination_city": "IXR",
                "route": "PAT_IXR",
                "departure_time": "Midnight",
                "arrival_time": "Dawn",
                "cabin_class": "FirstClass",
                "booking_window": "unknown_bucket",
                "stops": 1,
                "duration_minutes": 150.0,
                "days_left": 10,
                "is_peak_departure": 0,
            }
        ])
        transformed = preprocessor.transform(unseen_data[ALL_MODEL_FEATURES])
        assert transformed.shape[0] == 1
        assert not np.isnan(transformed).any()


class TestPredictorInputValidation:
    def test_missing_origin_raises_error(self):
        predictor = FarePredictor()
        with pytest.raises(InvalidInputError, match="Both origin"):
            predictor.predict_fare({"destination": "BOM"})

    def test_missing_destination_raises_error(self):
        predictor = FarePredictor()
        with pytest.raises(InvalidInputError, match="Both origin"):
            predictor.predict_fare({"origin": "DEL"})

    def test_same_origin_and_destination_raises_error(self):
        predictor = FarePredictor()
        with pytest.raises(InvalidInputError, match="Origin and destination cities cannot be identical"):
            predictor.predict_fare({"origin": "DEL", "destination": "DEL"})

    def test_unloaded_nonexistent_model_raises_error(self):
        predictor = FarePredictor(model_path="/nonexistent/model.joblib")
        with pytest.raises(ModelNotLoadedError, match="Model artifact not found"):
            predictor.predict_fare({"origin": "DEL", "destination": "BOM"})


class TestPredictionOutputAndSanity:
    @pytest.fixture(autouse=True)
    def setup_predictor(self):
        self.predictor = get_predictor()
        # Only test inference if model is trained and saved
        if not self.predictor.model_path.exists():
            pytest.skip("Trained model artifact not available yet for inference tests.")
        self.predictor.load()

    def test_valid_prediction_structure(self):
        flight = {
            "origin": "Delhi",
            "destination": "Mumbai",
            "airline": "IndiGo",
            "cabin_class": "Economy",
            "days_left": 25,
            "departure_time": "Morning",
            "stops": 0,
        }
        res = self.predictor.predict_fare(flight)

        required_keys = [
            "predicted_fare",
            "lower_estimate",
            "upper_estimate",
            "currency",
            "model",
            "data_basis",
            "route",
            "airline",
            "cabin_class",
            "days_left",
            "prediction_uncertainty_margin",
        ]
        for key in required_keys:
            assert key in res, f"Missing key '{key}' in prediction response."

        assert res["currency"] == "INR"
        assert res["route"] == "DEL_BOM"
        assert res["cabin_class"] == "Economy"
        assert res["lower_estimate"] <= res["predicted_fare"] <= res["upper_estimate"]
        assert res["predicted_fare"] >= 800

    def test_business_class_premium(self):
        """Business class prediction must exceed Economy for same route and lead time."""
        econ = self.predictor.predict_fare({
            "origin": "DEL",
            "destination": "BOM",
            "airline": "Vistara",
            "cabin_class": "Economy",
            "days_left": 20,
            "stops": 0,
        })
        biz = self.predictor.predict_fare({
            "origin": "DEL",
            "destination": "BOM",
            "airline": "Vistara",
            "cabin_class": "Business",
            "days_left": 20,
            "stops": 0,
        })
        assert biz["predicted_fare"] > econ["predicted_fare"] * 1.5

    def test_last_minute_price_surge(self):
        """1-day advance booking should predict higher than 30-day advance booking."""
        last_min = self.predictor.predict_fare({
            "origin": "DEL",
            "destination": "BLR",
            "airline": "IndiGo",
            "cabin_class": "Economy",
            "days_left": 1,
            "stops": 0,
        })
        early = self.predictor.predict_fare({
            "origin": "DEL",
            "destination": "BLR",
            "airline": "IndiGo",
            "cabin_class": "Economy",
            "days_left": 35,
            "stops": 0,
        })
        assert last_min["predicted_fare"] > early["predicted_fare"]

    def test_predict_batch(self):
        flights = [
            {"origin": "DEL", "destination": "BOM", "days_left": 15},
            {"origin": "BOM", "destination": "BLR", "days_left": 5},
        ]
        batch_res = self.predictor.predict_batch(flights)
        assert len(batch_res) == 2
        assert batch_res[0]["route"] == "DEL_BOM"
        assert batch_res[1]["route"] == "BOM_BLR"

    def test_metadata_loading(self):
        metadata = self.predictor.get_metadata()
        assert "model_name" in metadata
        assert "target_variable" in metadata
        assert "champion_metrics" in metadata
        assert "prediction_range" in metadata
        assert metadata["champion_metrics"]["R2"] > 0.85
