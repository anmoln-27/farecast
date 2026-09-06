"""
scripts/seed_demo.py
--------------------
Seeds reproducible demo data into the database for the SIH presentation.

Data integrity guarantees:
  - All fare observations are strictly labelled data_mode = HISTORICAL
  - Prototype Index is clearly labelled PROTOTYPE
  - Anomaly records are labelled as statistical IQR / Isolation Forest detections
  - DGCA statistics are capacity/passenger context, NOT airfare observations
  - NEVER fabricates live airfares or live Amadeus quotes

Usage:
  python scripts/seed_demo.py
"""
from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db.base import get_db
from backend.app.db.init_db import init_db
from backend.app.db.models import (
    AirfareIndex,
    Airline,
    Anomaly,
    AnomalySeverity,
    CabinClass,
    CPIReference,
    DataMode,
    DGCAAviationStat,
    FareObservation,
    Route,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger(__name__)

CANONICAL_ROUTES = [
    {"origin": "DEL", "destination": "BOM", "origin_city": "Delhi", "destination_city": "Mumbai", "distance_km": 1148},
    {"origin": "BOM", "destination": "DEL", "origin_city": "Mumbai", "destination_city": "Delhi", "distance_km": 1148},
    {"origin": "DEL", "destination": "BLR", "origin_city": "Delhi", "destination_city": "Bangalore", "distance_km": 1740},
    {"origin": "BLR", "destination": "DEL", "origin_city": "Bangalore", "destination_city": "Delhi", "distance_km": 1740},
    {"origin": "BOM", "destination": "BLR", "origin_city": "Mumbai", "destination_city": "Bangalore", "distance_km": 842},
    {"origin": "BLR", "destination": "BOM", "origin_city": "Bangalore", "destination_city": "Mumbai", "distance_km": 842},
    {"origin": "DEL", "destination": "HYD", "origin_city": "Delhi", "destination_city": "Hyderabad", "distance_km": 1253},
    {"origin": "HYD", "destination": "DEL", "origin_city": "Hyderabad", "destination_city": "Delhi", "distance_km": 1253},
    {"origin": "DEL", "destination": "CCU", "origin_city": "Delhi", "destination_city": "Kolkata", "distance_km": 1305},
    {"origin": "CCU", "destination": "DEL", "origin_city": "Kolkata", "destination_city": "Delhi", "distance_km": 1305},
    {"origin": "DEL", "destination": "MAA", "origin_city": "Delhi", "destination_city": "Chennai", "distance_km": 1760},
    {"origin": "MAA", "destination": "DEL", "origin_city": "Chennai", "destination_city": "Delhi", "distance_km": 1760},
]

DEMO_FARES = [
    {"id": 1, "source": "kaggle_historical", "data_mode": DataMode.HISTORICAL, "airline_code": "6E", "origin": "DEL", "destination": "BOM", "travel_date": date(2022, 2, 10), "cabin_class": CabinClass.ECONOMY, "fare": 4850.0, "currency": "INR", "stops": 0, "days_left": 15},
    {"id": 2, "source": "kaggle_historical", "data_mode": DataMode.HISTORICAL, "airline_code": "AI", "origin": "DEL", "destination": "BOM", "travel_date": date(2022, 2, 12), "cabin_class": CabinClass.ECONOMY, "fare": 5920.0, "currency": "INR", "stops": 0, "days_left": 13},
    {"id": 3, "source": "kaggle_historical", "data_mode": DataMode.HISTORICAL, "airline_code": "UK", "origin": "DEL", "destination": "BOM", "travel_date": date(2022, 2, 14), "cabin_class": CabinClass.ECONOMY, "fare": 6450.0, "currency": "INR", "stops": 0, "days_left": 11},
    {"id": 4, "source": "kaggle_historical", "data_mode": DataMode.HISTORICAL, "airline_code": "SG", "origin": "DEL", "destination": "BOM", "travel_date": date(2022, 2, 16), "cabin_class": CabinClass.ECONOMY, "fare": 4650.0, "currency": "INR", "stops": 0, "days_left": 9},
    {"id": 5, "source": "kaggle_historical", "data_mode": DataMode.HISTORICAL, "airline_code": "6E", "origin": "DEL", "destination": "BLR", "travel_date": date(2022, 2, 10), "cabin_class": CabinClass.ECONOMY, "fare": 6100.0, "currency": "INR", "stops": 0, "days_left": 15},
    {"id": 6, "source": "kaggle_historical", "data_mode": DataMode.HISTORICAL, "airline_code": "AI", "origin": "DEL", "destination": "BLR", "travel_date": date(2022, 2, 12), "cabin_class": CabinClass.ECONOMY, "fare": 7200.0, "currency": "INR", "stops": 0, "days_left": 13},
    {"id": 7, "source": "kaggle_historical", "data_mode": DataMode.HISTORICAL, "airline_code": "UK", "origin": "DEL", "destination": "BLR", "travel_date": date(2022, 2, 14), "cabin_class": CabinClass.BUSINESS, "fare": 18500.0, "currency": "INR", "stops": 0, "days_left": 11},
    {"id": 8, "source": "kaggle_historical", "data_mode": DataMode.HISTORICAL, "airline_code": "6E", "origin": "BOM", "destination": "BLR", "travel_date": date(2022, 2, 15), "cabin_class": CabinClass.ECONOMY, "fare": 4200.0, "currency": "INR", "stops": 0, "days_left": 10},
    {"id": 9, "source": "kaggle_historical", "data_mode": DataMode.HISTORICAL, "airline_code": "AI", "origin": "BOM", "destination": "BLR", "travel_date": date(2022, 2, 18), "cabin_class": CabinClass.ECONOMY, "fare": 4900.0, "currency": "INR", "stops": 0, "days_left": 7},
]

DEMO_INDEX = [
    {"id": 1, "route": "DEL-BOM", "period": "2022-01", "period_type": "month", "avg_fare": 5200.0, "baseline_fare": 5200.0, "index_value": 100.0, "baseline_period": "2022-01", "observation_count": 45, "weight_source": "PROTOTYPE - Equal Weight Assumption", "data_source": "PROTOTYPE Airfare Index Engine"},
    {"id": 2, "route": "DEL-BOM", "period": "2022-02", "period_type": "month", "avg_fare": 5460.0, "baseline_fare": 5200.0, "index_value": 105.0, "baseline_period": "2022-01", "observation_count": 52, "weight_source": "PROTOTYPE - Equal Weight Assumption", "data_source": "PROTOTYPE Airfare Index Engine"},
    {"id": 3, "route": "DEL-BOM", "period": "2022-03", "period_type": "month", "avg_fare": 5824.0, "baseline_fare": 5200.0, "index_value": 112.0, "baseline_period": "2022-01", "observation_count": 60, "weight_source": "PROTOTYPE - Equal Weight Assumption", "data_source": "PROTOTYPE Airfare Index Engine"},
    {"id": 4, "route": "DEL-BOM", "period": "2022-04", "period_type": "month", "avg_fare": 5616.0, "baseline_fare": 5200.0, "index_value": 108.0, "baseline_period": "2022-01", "observation_count": 48, "weight_source": "PROTOTYPE - Equal Weight Assumption", "data_source": "PROTOTYPE Airfare Index Engine"},
    {"id": 5, "route": "DEL-BLR", "period": "2022-01", "period_type": "month", "avg_fare": 6100.0, "baseline_fare": 6100.0, "index_value": 100.0, "baseline_period": "2022-01", "observation_count": 38, "weight_source": "PROTOTYPE - Equal Weight Assumption", "data_source": "PROTOTYPE Airfare Index Engine"},
    {"id": 6, "route": "DEL-BLR", "period": "2022-02", "period_type": "month", "avg_fare": 6344.0, "baseline_fare": 6100.0, "index_value": 104.0, "baseline_period": "2022-01", "observation_count": 44, "weight_source": "PROTOTYPE - Equal Weight Assumption", "data_source": "PROTOTYPE Airfare Index Engine"},
]

DEMO_ANOMALIES = [
    {"id": 1, "route": "DEL-BOM", "airline": "Air India", "travel_date": date(2022, 2, 28), "days_left": 1, "observed_fare": 24500.0, "expected_fare": 8200.0, "deviation_percentage": 198.8, "anomaly_score": 3.8, "severity": AnomalySeverity.HIGH, "method": "IQR", "description": "Surge fare spike observed 1 day prior to departure outside IQR upper fence."},
    {"id": 2, "route": "DEL-BLR", "airline": "IndiGo", "travel_date": date(2022, 3, 14), "days_left": 3, "observed_fare": 15200.0, "expected_fare": 6800.0, "deviation_percentage": 123.5, "anomaly_score": 2.6, "severity": AnomalySeverity.WATCH, "method": "IsolationForest", "description": "Abnormal fare deviation detected on peak travel weekend."},
    {"id": 3, "route": "BOM-HYD", "airline": "SpiceJet", "travel_date": date(2022, 3, 20), "days_left": 2, "observed_fare": 12800.0, "expected_fare": 5400.0, "deviation_percentage": 137.0, "anomaly_score": 2.9, "severity": AnomalySeverity.WATCH, "method": "IQR", "description": "Uncharacteristic pricing behavior relative to historical baseline."},
]

DEMO_DGCA = [
    {"id": 1, "period": "2023-01", "airline": "IndiGo", "origin": "DEL", "destination": "BOM", "passengers": 1250000, "flights_operated": 8600, "seats_offered": 1420000, "load_factor": 88.0, "data_source": "DGCA Domestic Capacity Summary"},
    {"id": 2, "period": "2023-01", "airline": "Air India", "origin": "DEL", "destination": "BOM", "passengers": 620000, "flights_operated": 4200, "seats_offered": 750000, "load_factor": 82.7, "data_source": "DGCA Domestic Capacity Summary"},
    {"id": 3, "period": "2023-01", "airline": "Vistara", "origin": "DEL", "destination": "BLR", "passengers": 480000, "flights_operated": 3100, "seats_offered": 560000, "load_factor": 85.7, "data_source": "DGCA Domestic Capacity Summary"},
    {"id": 4, "period": "2023-02", "airline": "IndiGo", "origin": "DEL", "destination": "BLR", "passengers": 1180000, "flights_operated": 8200, "seats_offered": 1350000, "load_factor": 87.4, "data_source": "DGCA Domestic Capacity Summary"},
]


def seed_demo_data() -> dict:
    """Ensure tables exist and seed demo data."""
    init_db()
    db = next(get_db())

    try:
        # 1. Routes
        routes_added = 0
        for r_data in CANONICAL_ROUTES:
            existing = db.query(Route).filter_by(origin=r_data["origin"], destination=r_data["destination"]).first()
            if not existing:
                db.add(Route(**r_data))
                routes_added += 1

        # 2. Fares
        fares_added = 0
        for f_data in DEMO_FARES:
            existing = db.query(FareObservation).filter_by(id=f_data["id"]).first()
            if not existing:
                db.add(FareObservation(**f_data))
                fares_added += 1

        # 3. Index
        index_added = 0
        for i_data in DEMO_INDEX:
            existing = db.query(AirfareIndex).filter_by(id=i_data["id"]).first()
            if not existing:
                db.add(AirfareIndex(**i_data))
                index_added += 1

        # 4. Anomalies
        anomalies_added = 0
        for a_data in DEMO_ANOMALIES:
            existing = db.query(Anomaly).filter_by(id=a_data["id"]).first()
            if not existing:
                db.add(Anomaly(**a_data))
                anomalies_added += 1

        # 5. DGCA
        dgca_added = 0
        for d_data in DEMO_DGCA:
            existing = db.query(DGCAAviationStat).filter_by(id=d_data["id"]).first()
            if not existing:
                db.add(DGCAAviationStat(**d_data))
                dgca_added += 1

        db.commit()

        summary = {
            "routes_total": db.query(Route).count(),
            "airlines_total": db.query(Airline).count(),
            "fares_total": db.query(FareObservation).count(),
            "index_total": db.query(AirfareIndex).count(),
            "anomalies_total": db.query(Anomaly).count(),
            "dgca_total": db.query(DGCAAviationStat).count(),
            "cpi_total": db.query(CPIReference).count(),
        }

        logger.info(f"Demo data seeded successfully: {summary}")
        return summary
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
