"""
tests/test_nso_rbi_api.py
-------------------------
Tests for the NSO & RBI Regulatory Consumption API endpoints:
- GET /api/v1/nso/apix
- GET /api/v1/nso/apix/export
- GET /api/v1/rbi/macro-feed
- GET /api/v1/analytics/backtest-results
- GET /api/index with frequency and sub_index filters
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_nso_apix_endpoint(client):
    resp = client.get("/api/v1/nso/apix?frequency=monthly&sub_index=COMPOSITE")
    assert resp.status_code == 200
    data = resp.json()
    assert "institution" in data
    assert "headline_apix" in data
    assert "data" in data
    assert data["frequency"] == "monthly"
    assert data["sub_index"] == "COMPOSITE"
    assert "methodology" in data


def test_nso_apix_export_csv(client):
    resp = client.get("/api/v1/nso/apix/export?frequency=monthly")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "Content-Disposition" in resp.headers
    csv_text = resp.text
    assert "Period" in csv_text
    assert "Route" in csv_text
    assert "APIx_Index_Value" in csv_text


def test_rbi_macro_feed(client):
    resp = client.get("/api/v1/rbi/macro-feed")
    assert resp.status_code == 200
    data = resp.json()
    assert "core_indicators" in data
    assert "headline_apix" in data["core_indicators"]
    assert "advance_booking_volatility_spread_pct" in data["core_indicators"]
    assert "inflation_signal" in data["core_indicators"]
    assert "dgca_benchmark_alignment" in data
    assert "sector_hotspots" in data


def test_backtest_results_endpoint(client):
    # Empirical mode (default)
    resp = client.get("/api/v1/analytics/backtest-results?mode=empirical")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["validation_mode"] == "EMPIRICAL_HISTORICAL_OUT_OF_SAMPLE"
    assert "metrics" in data
    assert "pearson_correlation" in data["metrics"]
    assert "mape_percent" in data["metrics"]
    assert "tracking_error" in data["metrics"]

    # Demonstration mode
    resp_demo = client.get("/api/v1/analytics/backtest-results?mode=demonstration")
    assert resp_demo.status_code == 200
    data_demo = resp_demo.json()
    assert data_demo["status"] == "success"
    assert data_demo["metrics"]["pearson_correlation"] >= 0.85
    assert data_demo["metrics"]["mape_percent"] <= 8.0
    assert data_demo["validation_status"] == "VALIDATED"


def test_index_filters(client):
    resp = client.get("/api/index?frequency=monthly&sub_index=COMPOSITE")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
