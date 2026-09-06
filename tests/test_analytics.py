"""
tests/test_analytics.py
-----------------------
Tests for Phase 3 analytics: Airfare Price Index and Anomaly Detection.
"""
from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.db.models import FareObservation, DataMode, CabinClass, AirfareIndex, Anomaly
from backend.app.analytics.index_engine import calculate_baseline, generate_price_index
from backend.app.analytics.anomaly import detect_anomalies_iqr, detect_anomalies_isolation_forest


@pytest.fixture(scope="module")
def analytics_session():
    # Use in-memory SQLite for testing analytics logic
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Seed data
    fares = []
    fare_id = 1
    # Baseline period data (2022-01) for DEL-BOM
    for i in range(15):
        fares.append(FareObservation(
            id=fare_id,
            source="test",
            data_mode=DataMode.HISTORICAL,
            origin="DEL",
            destination="BOM",
            travel_date=date(2022, 1, 15),
            cabin_class=CabinClass.ECONOMY,
            fare=5000 + (i * 100),
            days_left=30
        ))
        fare_id += 1
        
    # Target period data (2022-02) for DEL-BOM - slightly higher prices
    for i in range(10):
        fares.append(FareObservation(
            id=fare_id,
            source="test",
            data_mode=DataMode.HISTORICAL,
            origin="DEL",
            destination="BOM",
            travel_date=date(2022, 2, 15),
            cabin_class=CabinClass.ECONOMY,
            fare=6000 + (i * 100),
            days_left=15
        ))
        fare_id += 1
        
    # Anomaly records - IQR (extreme values)
    fares.append(FareObservation(
        id=fare_id,
        source="test", data_mode=DataMode.HISTORICAL, origin="DEL", destination="BOM",
        travel_date=date(2022, 2, 16), cabin_class=CabinClass.ECONOMY, fare=15000, days_left=2
    ))
    fare_id += 1
    fares.append(FareObservation(
        id=fare_id,
        source="test", data_mode=DataMode.HISTORICAL, origin="DEL", destination="BOM",
        travel_date=date(2022, 2, 16), cabin_class=CabinClass.ECONOMY, fare=1000, days_left=40
    ))
    fare_id += 1
    
    # Add enough records for Isolation Forest to work (needs >= 50)
    for i in range(50):
        fares.append(FareObservation(
            id=fare_id,
            source="test", data_mode=DataMode.HISTORICAL, origin="BLR", destination="DEL",
            travel_date=date(2022, 3, 1), cabin_class=CabinClass.ECONOMY, fare=4000 + (i * 50), days_left=20
        ))
        fare_id += 1
    # IF outliers
    fares.append(FareObservation(
        id=fare_id,
        source="test", data_mode=DataMode.HISTORICAL, origin="BLR", destination="DEL",
        travel_date=date(2022, 3, 2), cabin_class=CabinClass.ECONOMY, fare=25000, days_left=1
    ))
    fare_id += 1
        
    session.add_all(fares)
    session.commit()
    
    yield session
    
    session.close()


def test_baseline_calculation(analytics_session):
    # Test baseline over the entire 2022-01 period
    baseline = calculate_baseline(analytics_session, start_date=date(2022, 1, 1), end_date=date(2022, 1, 31))
    
    assert "DEL-BOM" in baseline
    # Average of 5000 + (0..14)*100 => 5000 + 700 = 5700
    assert baseline["DEL-BOM"] == 5700.0


def test_index_generation(analytics_session):
    baseline = {"DEL-BOM": 5700.0}
    
    # Generate index for Feb 2022
    indices = generate_price_index(
        analytics_session, 
        target_start_date=date(2022, 2, 1), 
        target_end_date=date(2022, 2, 28),
        period_label="2022-02",
        baseline_fares=baseline,
        baseline_period_label="2022-01"
    )
    
    assert len(indices) == 1
    idx = indices[0]
    assert idx.route == "DEL-BOM"
    assert idx.period == "2022-02"
    # Average of Feb fares: 10 regular (6000 + 0..9*100) + 2 anomalies (15000, 1000)
    # 6000, 6100, 6200... 6900 => sum 64500
    # + 15000 + 1000 = 80500 / 12 = 6708.33
    assert abs(idx.avg_fare - 6708.33) < 1.0
    assert abs(idx.index_value - (idx.avg_fare / 5700.0) * 100.0) < 0.1
    assert idx.weight_source == "PROTOTYPE - Equal Weight Assumption"
    
    # DB persistence check
    db_idx = analytics_session.query(AirfareIndex).filter_by(period="2022-02", route="DEL-BOM").first()
    assert db_idx is not None
    assert db_idx.index_value == idx.index_value


def test_insufficient_data_handling(analytics_session):
    baseline = {"DEL-BOM": 5700.0, "XYZ-ABC": 1000.0}
    
    # Add a route with just 2 records (below the threshold of 5 for index)
    fares = [
        FareObservation(id=999, source="test", data_mode=DataMode.HISTORICAL, origin="XYZ", destination="ABC", 
                        travel_date=date(2022, 4, 1), fare=1000),
        FareObservation(id=1000, source="test", data_mode=DataMode.HISTORICAL, origin="XYZ", destination="ABC", 
                        travel_date=date(2022, 4, 1), fare=1100),
    ]
    analytics_session.add_all(fares)
    analytics_session.commit()
    
    indices = generate_price_index(
        analytics_session,
        target_start_date=date(2022, 4, 1),
        target_end_date=date(2022, 4, 30),
        period_label="2022-04",
        baseline_fares=baseline
    )
    
    # Should be empty because count < 5
    assert len(indices) == 0


def test_anomaly_detection_iqr(analytics_session):
    # Feb 2022 has the anomalies
    anomalies = detect_anomalies_iqr(
        analytics_session, 
        route_origin="DEL", 
        route_destination="BOM",
        start_date=date(2022, 2, 1),
        end_date=date(2022, 2, 28)
    )
    
    # We inserted a 15000 and 1000 fare. Normal is ~6000-6900.
    assert len(anomalies) >= 2
    fares = [a.observed_fare for a in anomalies]
    assert 15000 in fares
    assert 1000 in fares
    
    # Check that they were persisted
    db_anomalies = analytics_session.query(Anomaly).filter_by(method="IQR").all()
    assert len(db_anomalies) >= 2


def test_anomaly_detection_iforest(analytics_session):
    # March 2022 has the BLR-DEL records
    anomalies = detect_anomalies_isolation_forest(
        analytics_session, 
        route_origin="BLR", 
        route_destination="DEL",
        start_date=date(2022, 3, 1),
        end_date=date(2022, 3, 31)
    )
    
    # We inserted a 25000 outlier among 4000-6500 normals.
    assert len(anomalies) > 0
    fares = [a.observed_fare for a in anomalies]
    assert 25000 in fares

    # Check that they were persisted
    db_anomalies = analytics_session.query(Anomaly).filter_by(method="IsolationForest").all()
    assert len(db_anomalies) > 0
