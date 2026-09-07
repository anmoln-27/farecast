"""
tests/test_apix_engine.py
-------------------------
Tests for Advanced APIx Price Index Construction Engine:
- Laspeyres & Fisher Ideal formulations
- DGCA passenger traffic weighting
- Multi-window stratification (T+1, T+7, T+15, T+30, T+45)
- Sub-indices & National Headline APIx calculation
"""
from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.db.models import FareObservation, DataMode, CabinClass
from backend.app.analytics.index_engine import (
    DGCA_ROUTE_TRAFFIC_WEIGHTS,
    ADVANCE_WINDOW_WEIGHTS,
    compute_apix_index,
)


@pytest.fixture
def apix_test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed observations for DEL-BOM and BLR-DEL across advance windows
    obs = []
    fid = 1

    # DEL-BOM target month (2023-05)
    windows_del_bom = {"T+1": 12000.0, "T+7": 7500.0, "T+15": 5200.0, "T+30": 4200.0, "T+45": 3800.0}
    for win, price in windows_del_bom.items():
        for _ in range(5):
            obs.append(FareObservation(
                id=fid,
                source="scraper",
                data_mode=DataMode.LIVE,
                airline_code="6E",
                origin="DEL",
                destination="BOM",
                travel_date=date(2023, 5, 15),
                advance_window=win,
                fare=price,
                base_fare=price * 0.7,
                taxes=price * 0.2,
                udf_charge=300.0,
                convenience_fee=350.0,
                total_fare=price,
                status="AVAILABLE",
            ))
            fid += 1

    # DEL-BLR target month (2023-05)
    windows_del_blr = {"T+1": 14000.0, "T+7": 8500.0, "T+15": 6000.0, "T+30": 4800.0, "T+45": 4400.0}
    for win, price in windows_del_blr.items():
        for _ in range(5):
            obs.append(FareObservation(
                id=fid,
                source="scraper",
                data_mode=DataMode.LIVE,
                airline_code="AI",
                origin="DEL",
                destination="BLR",
                travel_date=date(2023, 5, 15),
                advance_window=win,
                fare=price,
                base_fare=price * 0.7,
                taxes=price * 0.2,
                udf_charge=300.0,
                convenience_fee=350.0,
                total_fare=price,
                status="AVAILABLE",
            ))
            fid += 1

    session.add_all(obs)
    session.commit()
    yield session
    session.close()


def test_dgca_traffic_weights_presence():
    assert "DEL-BOM" in DGCA_ROUTE_TRAFFIC_WEIGHTS
    assert "DEL-BLR" in DGCA_ROUTE_TRAFFIC_WEIGHTS
    assert DGCA_ROUTE_TRAFFIC_WEIGHTS["DEL-BOM"] > DGCA_ROUTE_TRAFFIC_WEIGHTS["BLR-HYD"]


def test_advance_window_weights_sum_to_one():
    total_w = sum(ADVANCE_WINDOW_WEIGHTS.values())
    assert abs(total_w - 1.0) < 1e-6


def test_laspeyres_apix_calculation(apix_test_db):
    baselines = {
        "DEL-BOM": 5000.0,
        "DEL-BLR": 5500.0,
    }
    records = compute_apix_index(
        session=apix_test_db,
        target_start_date=date(2023, 5, 1),
        target_end_date=date(2023, 5, 31),
        period_label="2023-05",
        baseline_fares=baselines,
        frequency="monthly",
        formula="Laspeyres",
        save_to_db=True,
    )

    assert len(records) > 0

    # Verify AGGREGATE headline index exists
    headline = next((r for r in records if r.route == "AGGREGATE"), None)
    assert headline is not None
    assert headline.index_value > 100.0  # Fares surged above baseline
    assert headline.index_formula == "Laspeyres"
    assert headline.frequency == "monthly"

    # Verify sub-indices exist
    sub_spot = next((r for r in records if r.sub_index == "T+1_SPOT" and r.route == "DEL-BOM"), None)
    sub_early = next((r for r in records if r.sub_index == "T+45_EARLY" and r.route == "DEL-BOM"), None)
    assert sub_spot is not None
    assert sub_early is not None
    assert sub_spot.index_value > sub_early.index_value  # Spot surge is higher than early bird


def test_fisher_ideal_apix_calculation(apix_test_db):
    baselines = {"DEL-BOM": 5000.0, "DEL-BLR": 5500.0}
    records = compute_apix_index(
        session=apix_test_db,
        target_start_date=date(2023, 5, 1),
        target_end_date=date(2023, 5, 31),
        period_label="2023-05",
        baseline_fares=baselines,
        frequency="monthly",
        formula="Fisher",
        save_to_db=False,
    )
    headline = next((r for r in records if r.route == "AGGREGATE"), None)
    assert headline is not None
    assert headline.index_formula == "Fisher"
