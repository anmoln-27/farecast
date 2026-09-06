"""
backend/app/db/models.py
------------------------
SQLAlchemy ORM models matching the full database schema.

Tables:
  - airlines
  - routes
  - fare_observations       (common schema — all airfare data)
  - airfare_index           (computed prototype price index)
  - dgca_aviation_stats     (DGCA traffic/capacity data)
  - cpi_reference           (MoSPI/CPI benchmark data)
  - prediction_results      (ML model outputs)
  - anomalies               (anomaly detection outputs)
"""
from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


# ─────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────

class DataMode(str, enum.Enum):
    LIVE = "LIVE"
    HISTORICAL = "HISTORICAL"
    DEMO = "DEMO"


class CabinClass(str, enum.Enum):
    ECONOMY = "Economy"
    PREMIUM_ECONOMY = "Premium Economy"
    BUSINESS = "Business"
    FIRST = "First"


class AnomalySeverity(str, enum.Enum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    HIGH = "HIGH"


# ─────────────────────────────────────────────
# Airlines
# ─────────────────────────────────────────────

class Airline(Base):
    __tablename__ = "airlines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    country = Column(String(50), default="India")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    fare_observations = relationship("FareObservation", back_populates="airline_ref")


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    origin = Column(String(10), nullable=False)
    destination = Column(String(10), nullable=False)
    origin_city = Column(String(100))
    destination_city = Column(String(100))
    distance_km = Column(Float)
    is_domestic = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("origin", "destination", name="uq_routes_od"),
    )


# ─────────────────────────────────────────────
# Fare Observations (Common Schema)
# ─────────────────────────────────────────────

class FareObservation(Base):
    """
    Central table for all airfare data regardless of source.
    Each record represents one bookable fare observation.
    """
    __tablename__ = "fare_observations"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)

    # Provenance
    source = Column(String(50), nullable=False, index=True)
    # e.g. "kaggle", "github_full_fare", "amadeus", "demo"
    data_mode = Column(
        Enum(DataMode), nullable=False, default=DataMode.HISTORICAL, index=True
    )

    # Airline / Flight
    airline_code = Column(String(10), ForeignKey("airlines.code"), index=True)
    flight_number = Column(String(20))

    # Route
    origin = Column(String(10), nullable=False, index=True)
    destination = Column(String(10), nullable=False, index=True)

    # Travel timing
    travel_date = Column(Date, nullable=False, index=True)
    booking_date = Column(Date)
    departure_time = Column(String(20))   # stored as HH:MM or period label
    arrival_time = Column(String(20))

    # Trip details
    stops = Column(Integer, default=0)
    duration_minutes = Column(Integer)
    cabin_class = Column(Enum(CabinClass), default=CabinClass.ECONOMY, index=True)

    # Fare
    fare = Column(Float, nullable=False)
    currency = Column(String(5), default="INR")

    # Metadata
    collected_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Days before travel at time of booking/observation
    days_left = Column(Integer)

    # Relationships
    airline_ref = relationship("Airline", back_populates="fare_observations")


# ─────────────────────────────────────────────
# Prototype Airfare Price Index
# ─────────────────────────────────────────────

class AirfareIndex(Base):
    """
    Stores computed Prototype Airfare Price Index values.
    NOT an official Government of India index.
    """
    __tablename__ = "airfare_index"

    id = Column(Integer, primary_key=True, autoincrement=True)

    route = Column(String(20), index=True)   # e.g. "DEL-BOM" or "AGGREGATE"
    airline = Column(String(50))             # specific airline or "ALL"

    period = Column(String(20), nullable=False)  # e.g. "2023-01" or "2023-Q1"
    period_type = Column(String(10), default="month")  # "month", "quarter", "year"

    avg_fare = Column(Float)
    baseline_fare = Column(Float)
    index_value = Column(Float)              # (avg_fare / baseline_fare) * 100
    baseline_period = Column(String(20))
    observation_count = Column(Integer)

    weight = Column(Float)                   # prototype weight if aggregated
    weight_source = Column(String(100))      # "prototype" / official source note

    data_source = Column(String(100))
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────
# DGCA Aviation Statistics
# ─────────────────────────────────────────────

class DGCAAviationStat(Base):
    """
    Official DGCA aviation statistics.
    This is NOT airfare data — it is aviation activity/capacity data.
    """
    __tablename__ = "dgca_aviation_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)

    period = Column(String(20), nullable=False, index=True)   # "2023-01"
    airline = Column(String(50))
    origin = Column(String(10))
    destination = Column(String(10))

    passengers = Column(BigInteger)
    flights_operated = Column(Integer)
    seats_offered = Column(Integer)
    load_factor = Column(Float)           # percentage

    data_source = Column(String(100), default="DGCA")
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────
# CPI Reference (MoSPI)
# ─────────────────────────────────────────────

class CPIReference(Base):
    """
    MoSPI/CPI benchmark data for methodological context.
    NOT used as airfare observations or ML training data.
    """
    __tablename__ = "cpi_reference"

    id = Column(Integer, primary_key=True, autoincrement=True)

    source = Column(String(50), default="MoSPI")
    indicator = Column(String(200), nullable=False)
    # e.g. "CPI (Rural+Urban) - Transport & Communication"

    period = Column(String(20), nullable=False)   # "2023-01"
    value = Column(Float)
    base_year = Column(String(20))                # e.g. "2012"
    description = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────
# ML Prediction Results
# ─────────────────────────────────────────────

class PredictionResult(Base):
    __tablename__ = "prediction_results"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)

    model_name = Column(String(100), nullable=False)
    model_version = Column(String(50))

    airline = Column(String(50))
    origin = Column(String(10))
    destination = Column(String(10))
    travel_date = Column(Date)
    cabin_class = Column(String(30))
    stops = Column(Integer)
    duration_minutes = Column(Integer)
    days_left = Column(Integer)
    departure_time = Column(String(20))

    predicted_fare = Column(Float)
    lower_bound = Column(Float)
    upper_bound = Column(Float)

    # Evaluation (only populated on test-set predictions)
    actual_fare = Column(Float)
    mae = Column(Float)
    rmse = Column(Float)
    r2 = Column(Float)

    predicted_at = Column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────
# Anomalies
# ─────────────────────────────────────────────

class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)

    fare_observation_id = Column(BigInteger, ForeignKey("fare_observations.id"))

    route = Column(String(20), nullable=False, index=True)
    airline = Column(String(50))
    travel_date = Column(Date)
    days_left = Column(Integer)

    observed_fare = Column(Float)
    expected_fare = Column(Float)
    deviation_percentage = Column(Float)
    anomaly_score = Column(Float)

    severity = Column(Enum(AnomalySeverity), default=AnomalySeverity.NORMAL)
    method = Column(String(50))  # e.g. "IQR", "IsolationForest"
    description = Column(Text)   # human-readable explanation

    detected_at = Column(DateTime(timezone=True), server_default=func.now())
