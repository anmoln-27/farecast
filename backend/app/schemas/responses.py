"""
backend/app/schemas/responses.py
---------------------------------
Pydantic v2 response models for all Phase 4 API endpoints.
These schemas are API contracts — they do NOT replace ORM models.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Generic wrappers
# ─────────────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "4.0"
    demo_mode: bool
    amadeus_configured: bool
    ignav_configured: bool = False


class PaginationMeta(BaseModel):
    total: int
    limit: int
    offset: int
    avg_fare: Optional[float] = None
    min_fare: Optional[float] = None
    max_fare: Optional[float] = None


# ─────────────────────────────────────────────────────────────────────────────
# Fares
# ─────────────────────────────────────────────────────────────────────────────

class FareRecord(BaseModel):
    id: int
    source: str
    data_mode: str
    airline_code: Optional[str] = None
    origin: str
    destination: str
    travel_date: Optional[date] = None
    cabin_class: Optional[str] = None
    fare: float
    currency: str = "INR"
    stops: Optional[int] = None
    days_left: Optional[int] = None
    collected_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class FaresResponse(BaseModel):
    data: List[FareRecord]
    meta: PaginationMeta


class FareTrendPoint(BaseModel):
    date: str
    avgFare: float
    count: int


class AirlineComparisonItem(BaseModel):
    airlineCode: str
    avgFare: float
    count: int


class RouteComparisonItem(BaseModel):
    route: str
    avgFare: float
    count: int


class FareSummaryStats(BaseModel):
    total_observations: int
    avg_fare: Optional[float] = None
    min_fare: Optional[float] = None
    max_fare: Optional[float] = None


class FareAnalyticsResponse(BaseModel):
    status: str = "success"
    summary: FareSummaryStats
    trend: List[FareTrendPoint]
    airline_comparison: List[AirlineComparisonItem]
    route_comparison: List[RouteComparisonItem]


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

class RouteRecord(BaseModel):
    id: int
    origin: str
    destination: str
    origin_city: Optional[str] = None
    destination_city: Optional[str] = None
    distance_km: Optional[float] = None
    is_domestic: bool = True

    model_config = {"from_attributes": True}


class RoutesResponse(BaseModel):
    data: List[RouteRecord]
    total: int


# ─────────────────────────────────────────────────────────────────────────────
# Airlines
# ─────────────────────────────────────────────────────────────────────────────

class AirlineRecord(BaseModel):
    id: int
    code: str
    name: str
    country: Optional[str] = "India"
    is_active: bool = True

    model_config = {"from_attributes": True}


class AirlinesResponse(BaseModel):
    data: List[AirlineRecord]
    total: int


# ─────────────────────────────────────────────────────────────────────────────
# Index
# ─────────────────────────────────────────────────────────────────────────────

class IndexRecord(BaseModel):
    id: int
    route: Optional[str] = None
    airline: Optional[str] = None
    period: str
    period_type: Optional[str] = None
    frequency: Optional[str] = None
    index_formula: Optional[str] = None
    sub_index: Optional[str] = None
    dgca_weight: Optional[float] = None
    avg_fare: Optional[float] = None
    baseline_fare: Optional[float] = None
    index_value: Optional[float] = None
    baseline_period: Optional[str] = None
    observation_count: Optional[int] = None
    weight_source: Optional[str] = None
    data_source: Optional[str] = None

    model_config = {"from_attributes": True}


class IndexResponse(BaseModel):
    disclaimer: str = (
        "PROTOTYPE index only — NOT an official Government of India index. "
        "Computed from available historical fare observations."
    )
    data: List[IndexRecord]
    total: int


# ─────────────────────────────────────────────────────────────────────────────
# Prediction
# ─────────────────────────────────────────────────────────────────────────────

class PredictionRequest(BaseModel):
    origin: str = Field(..., description="IATA code or city name, e.g. DEL or Delhi")
    destination: str = Field(..., description="IATA code or city name, e.g. BOM or Mumbai")
    airline: Optional[str] = Field(default="IndiGo", description="Airline name")
    cabin_class: Optional[str] = Field(default="Economy", description="Economy or Business")
    departure_time: Optional[str] = Field(default="Morning")
    arrival_time: Optional[str] = Field(default="Afternoon")
    stops: Optional[int] = Field(default=0, ge=0, le=2)
    duration_minutes: Optional[int] = Field(default=130, gt=0)
    days_left: Optional[int] = Field(default=20, ge=1, le=365)


class PredictionResponse(BaseModel):
    predicted_fare: float
    lower_estimate: float
    upper_estimate: float
    currency: str = "INR"
    model: str
    data_basis: str
    route: str
    airline: str
    cabin_class: str
    days_left: int
    prediction_uncertainty_margin: float
    disclaimer: str = (
        "Prediction is based on historical patterns from publicly available datasets. "
        "Actual fares may differ significantly."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Anomalies
# ─────────────────────────────────────────────────────────────────────────────

class AnomalyRecord(BaseModel):
    id: int
    route: str
    airline: Optional[str] = None
    travel_date: Optional[date] = None
    days_left: Optional[int] = None
    observed_fare: Optional[float] = None
    expected_fare: Optional[float] = None
    deviation_percentage: Optional[float] = None
    anomaly_score: Optional[float] = None
    severity: Optional[str] = None
    method: Optional[str] = None
    description: Optional[str] = None
    detected_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AnomaliesResponse(BaseModel):
    data: List[AnomalyRecord]
    meta: PaginationMeta


# ─────────────────────────────────────────────────────────────────────────────
# DGCA
# ─────────────────────────────────────────────────────────────────────────────

class DGCARecord(BaseModel):
    id: int
    period: str
    airline: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    passengers: Optional[int] = None
    flights_operated: Optional[int] = None
    seats_offered: Optional[int] = None
    load_factor: Optional[float] = None
    data_source: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class DGCAResponse(BaseModel):
    disclaimer: str = (
        "Official DGCA aviation statistics. Represents traffic/capacity data, "
        "NOT airfare data."
    )
    data: List[DGCARecord]
    meta: PaginationMeta


# ─────────────────────────────────────────────────────────────────────────────
# CPI
# ─────────────────────────────────────────────────────────────────────────────

class CPIRecord(BaseModel):
    id: int
    source: Optional[str] = None
    indicator: str
    period: str
    value: Optional[float] = None
    base_year: Optional[str] = None
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class CPIResponse(BaseModel):
    disclaimer: str = (
        "MoSPI/CPI reference data. Provided as economic context only — "
        "NOT used as airfare observations or ML training data."
    )
    data: List[CPIRecord]
    total: int


# ─────────────────────────────────────────────────────────────────────────────
# Live / Amadeus
# ─────────────────────────────────────────────────────────────────────────────

class LiveFareOffer(BaseModel):
    source: str = "IGNAV"
    data_mode: str = "LIVE"
    origin: str
    destination: str
    airline_code: Optional[str] = None
    airline_name: Optional[str] = None
    flight_number: Optional[str] = None
    departure_datetime: Optional[str] = None
    arrival_datetime: Optional[str] = None
    duration_minutes: Optional[int] = None
    stops: int = 0
    cabin_class: str = "Economy"
    fare: float
    currency: str = "INR"
    fare_inr_estimate: Optional[float] = None
    collected_at: datetime
    segments: Optional[List[Dict[str, Any]]] = None


class LiveSearchResponse(BaseModel):
    data_mode: str
    source: str
    disclaimer: str
    offers: List[LiveFareOffer]
    total: int
    persisted_count: int = 0
    error_detail: Optional[str] = None


class LiveStatusResponse(BaseModel):
    demo_mode: bool
    amadeus_configured: bool
    ignav_configured: bool = False
    active_provider: str = "DEMO"
    amadeus_reachable: Optional[bool] = None
    mode_label: str
    message: str


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

class DashboardSummary(BaseModel):
    total_fare_observations: int
    total_routes: int
    total_airlines: int
    total_anomalies: int
    total_index_records: int
    total_dgca_records: int
    total_cpi_records: int
    demo_mode: bool
    amadeus_configured: bool
    ignav_configured: bool = False
    data_modes_present: List[str]
    # Aggregate fare statistics across ALL observations (full dataset, not paginated)
    avg_fare: Optional[float] = None
    min_fare: Optional[float] = None
    max_fare: Optional[float] = None
    disclaimer: str = (
        "FARECAST — Airfare Intelligence India. "
        "Prototype index values are NOT official Government of India statistics."
    )
