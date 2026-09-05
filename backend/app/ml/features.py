"""
backend/app/ml/features.py
--------------------------
Feature engineering and preprocessing pipeline for airfare prediction.

Transforms raw flight observations into clean, leak-free feature matrices.
Ensures identical preprocessing between training and real-time inference.
"""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from backend.app.services.schema import normalise_airline, normalise_city

# ── Feature Definitions ───────────────────────────────────────────────────────
CATEGORICAL_FEATURES = [
    "airline",
    "source_city",
    "destination_city",
    "route",
    "departure_time",
    "arrival_time",
    "cabin_class",
    "booking_window",
]

NUMERICAL_FEATURES = [
    "stops",
    "duration_minutes",
    "days_left",
    "is_peak_departure",
]

ALL_MODEL_FEATURES = CATEGORICAL_FEATURES + NUMERICAL_FEATURES


def categorize_booking_window(days_left: int | float | None) -> str:
    """Categorize booking lead time into behavioral demand buckets."""
    if days_left is None or pd.isna(days_left):
        return "standard"
    d = float(days_left)
    if d <= 3:
        return "last_minute"
    elif d <= 7:
        return "short_advance"
    elif d <= 20:
        return "standard"
    else:
        return "early_bird"


def is_peak_departure_time(departure_time: str | None) -> int:
    """Flag peak departure windows (Morning / Evening) in domestic air travel."""
    if not departure_time or pd.isna(departure_time):
        return 0
    dt_clean = str(departure_time).strip().lower()
    return 1 if dt_clean in ("morning", "evening") else 0


def prepare_features(
    df: pd.DataFrame,
    is_training: bool = False,
) -> tuple[pd.DataFrame, pd.Series | None]:
    """
    Standardize, engineer, and extract model features from a DataFrame.
    
    Accepts both raw Kaggle format ('Price', 'Source City', 'Class')
    and canonical database/API formats.

    Returns:
        (X, y): Engineered feature dataframe X, and target series y (or None).
    """
    df = df.copy()

    # Column name mapping
    rename_map = {
        "Airline": "airline",
        "Source City": "source_city",
        "source": "source_city",
        "origin": "source_city",
        "Destination City": "destination_city",
        "destination": "destination_city",
        "Departure Time": "departure_time",
        "Arrival Time": "arrival_time",
        "Stops": "stops",
        "Class": "cabin_class",
        "class": "cabin_class",
        "Duration": "duration",
        "Days Left": "days_left",
        "Price": "fare",
        "price": "fare",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Normalise categorical text
    if "airline" in df.columns:
        df["airline"] = df["airline"].astype(str).map(lambda x: normalise_airline(x))
    else:
        df["airline"] = "Unknown"

    if "source_city" in df.columns:
        df["source_city"] = df["source_city"].astype(str).map(lambda x: normalise_city(x))
    else:
        df["source_city"] = "DEL"

    if "destination_city" in df.columns:
        df["destination_city"] = df["destination_city"].astype(str).map(lambda x: normalise_city(x))
    else:
        df["destination_city"] = "BOM"

    # Route feature (origin_destination)
    df["route"] = df["source_city"] + "_" + df["destination_city"]

    # Departure & Arrival times
    for time_col in ["departure_time", "arrival_time"]:
        if time_col in df.columns:
            df[time_col] = df[time_col].astype(str).str.strip().str.title()
        else:
            df[time_col] = "Morning"

    # Cabin class
    if "cabin_class" in df.columns:
        df["cabin_class"] = df["cabin_class"].astype(str).str.strip().str.title()
        df["cabin_class"] = df["cabin_class"].replace({"Economy Class": "Economy", "Business Class": "Business"})
    else:
        df["cabin_class"] = "Economy"

    # Stops
    if "stops" in df.columns:
        def _parse_stops_val(v):
            if isinstance(v, (int, float)) and not pd.isna(v):
                return int(v)
            s = str(v).lower().strip()
            if "zero" in s or "non" in s:
                return 0
            if "one" in s or "1" in s:
                return 1
            return 2
        df["stops"] = df["stops"].map(_parse_stops_val)
    else:
        df["stops"] = 0

    # Duration in minutes
    if "duration_minutes" in df.columns:
        df["duration_minutes"] = pd.to_numeric(df["duration_minutes"], errors="coerce").fillna(120.0)
    elif "duration" in df.columns:
        # Check if duration is in hours (< 100) or minutes
        dur_numeric = pd.to_numeric(df["duration"], errors="coerce").fillna(2.0)
        # If mean duration is < 40, values are in hours -> convert to minutes
        if dur_numeric.mean() < 40:
            df["duration_minutes"] = dur_numeric * 60.0
        else:
            df["duration_minutes"] = dur_numeric
    else:
        df["duration_minutes"] = 120.0

    # Days left
    if "days_left" in df.columns:
        df["days_left"] = pd.to_numeric(df["days_left"], errors="coerce").clip(lower=1, upper=365).fillna(25)
    else:
        df["days_left"] = 25

    # Engineered features
    df["booking_window"] = df["days_left"].map(categorize_booking_window)
    df["is_peak_departure"] = df["departure_time"].map(is_peak_departure_time)

    # Extract target if present and requested
    y = None
    if is_training or "fare" in df.columns:
        if "fare" in df.columns:
            y = pd.to_numeric(df["fare"], errors="coerce")

    # Select only model features
    X = df[ALL_MODEL_FEATURES]

    return X, y


def build_preprocessor() -> ColumnTransformer:
    """
    Construct the ColumnTransformer pipeline for preprocessing.

    - Categorical features: OneHotEncoder(handle_unknown='ignore', sparse_output=False)
    - Numerical features: StandardScaler()
    """
    cat_transformer = Pipeline(
        steps=[
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    num_transformer = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", cat_transformer, CATEGORICAL_FEATURES),
            ("num", num_transformer, NUMERICAL_FEATURES),
        ],
        remainder="drop",
    )

    return preprocessor
