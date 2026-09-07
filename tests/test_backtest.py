"""
tests/test_backtest.py
----------------------
Unit tests for 30-Day DGCA Backtesting and Statistical Validation Suite.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.analytics.backtest import (
    seed_dgca_benchmarks,
    run_30day_backtest,
)


@pytest.fixture
def backtest_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    seed_dgca_benchmarks(session, days=35)
    yield session
    session.close()


def test_seed_dgca_benchmarks(backtest_session):
    from backend.app.db.models import DGCARouteFareBenchmark
    count = backtest_session.query(DGCARouteFareBenchmark).count()
    assert count >= 35 * 5  # 5 benchmark routes * 35 days


def test_run_30day_backtest_metrics(backtest_session):
    result = run_30day_backtest(session=backtest_session, seed_benchmarks_if_empty=False)
    assert result["status"] == "success"
    metrics = result["metrics"]
    assert metrics["pearson_correlation"] >= 0.85
    assert metrics["mape_percent"] <= 8.0
    assert metrics["directional_accuracy_percent"] >= 75.0
    assert result["validation_status"] == "VALIDATED"
    assert len(result["daily_comparison"]) >= 15
