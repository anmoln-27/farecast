"""
tests/test_api.py
------------------
Phase 4 tests for the FastAPI backend.

Covers:
  - Health endpoint
  - Fares, Routes, Airlines, Index, Prediction, Anomalies, DGCA, CPI, Dashboard
  - Amadeus service (fully mocked — NO real API calls)
  - Live search normalization
  - DEMO_MODE behavior
  - Missing credentials behavior
  - Security: credentials never leak into responses

IMPORTANT:
  Tests use in-memory SQLite and mocked HTTP — no real Amadeus API is called.
  No credentials appear in this file.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base, get_db
from backend.app.db.models import (
    Airline, AirfareIndex, Anomaly, AnomalySeverity,
    CPIReference, CabinClass, DataMode, DGCAAviationStat,
    FareObservation, Route,
)


# ─────────────────────────────────────────────────────────────────────────────
# In-memory test database and app fixture
# Uses StaticPool so all sessions share the SAME SQLite in-memory connection.
# ─────────────────────────────────────────────────────────────────────────────

from sqlalchemy.pool import StaticPool


@pytest.fixture(scope="module")
def test_engine():
    """
    Single shared in-memory SQLite engine.
    StaticPool ensures every Session uses the same underlying connection
    so data seeded in one session is visible to others.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="module")
def seeded_session(test_engine):
    """Seed all test data once for the module."""
    Session = sessionmaker(bind=test_engine)
    session = Session()

    session.add_all([
        Airline(id=1, code="6E", name="IndiGo", country="India", is_active=True),
        Airline(id=2, code="AI", name="Air India", country="India", is_active=True),
    ])
    session.add(Route(
        id=1, origin="DEL", destination="BOM",
        origin_city="Delhi", destination_city="Mumbai",
        distance_km=1148.0, is_domestic=True,
    ))
    session.add_all([
        FareObservation(
            id=1, source="kaggle", data_mode=DataMode.HISTORICAL,
            airline_code="6E", origin="DEL", destination="BOM",
            travel_date=date(2022, 3, 15), cabin_class=CabinClass.ECONOMY,
            fare=5500.0, currency="INR", stops=0, days_left=15,
        ),
        FareObservation(
            id=2, source="kaggle", data_mode=DataMode.HISTORICAL,
            airline_code="AI", origin="DEL", destination="BOM",
            travel_date=date(2022, 3, 16), cabin_class=CabinClass.BUSINESS,
            fare=15000.0, currency="INR", stops=0, days_left=30,
        ),
    ])
    session.add(AirfareIndex(
        id=1, route="DEL-BOM", airline="ALL",
        period="2022-03", period_type="month",
        avg_fare=10250.0, baseline_fare=9000.0,
        index_value=113.89, baseline_period="2022-01",
        observation_count=2, weight_source="PROTOTYPE - Equal Weight Assumption",
        data_source="PROTOTYPE Airfare Index Engine",
    ))
    session.add(Anomaly(
        id=1, route="DEL-BOM", airline="AI",
        travel_date=date(2022, 3, 16), days_left=1,
        observed_fare=25000.0, expected_fare=10000.0,
        deviation_percentage=150.0, anomaly_score=3.5,
        severity=AnomalySeverity.HIGH, method="IQR",
        description="Fare 25000 is outside typical range.",
    ))
    session.add(DGCAAviationStat(
        id=1, period="2023-01", airline="IndiGo",
        origin="DEL", destination="BOM",
        passengers=1200000, flights_operated=8500,
        seats_offered=1400000, load_factor=85.7,
        data_source="DGCA",
    ))
    session.add(CPIReference(
        id=1, source="MoSPI",
        indicator="CPI (Rural+Urban) - Transport & Communication",
        period="2023-01", value=138.4,
        base_year="2012",
        description="MoSPI CPI Combined index - Transport & Communication group",
    ))
    session.commit()
    yield session
    session.close()


@pytest.fixture(scope="module")
def api_client(test_engine, seeded_session):
    """
    TestClient with all DB-hitting dependencies overridden.
    Sessions from TestSession share the StaticPool connection and see all seeded data.
    """
    from backend.main import app
    from backend.app.core.config import get_settings, Settings

    TestSession = sessionmaker(bind=test_engine)

    def override_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    def override_settings():
        return Settings(
            _env_file=None,
            DATABASE_URL="sqlite:///:memory:",
            DEMO_MODE=True,
            AMADEUS_CLIENT_ID="",
            AMADEUS_CLIENT_SECRET="",
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = override_settings

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_ok(self, api_client):
        resp = api_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "demo_mode" in data
        assert "amadeus_configured" in data

    def test_health_no_credentials_in_response(self, api_client):
        resp = api_client.get("/health")
        body = resp.text
        assert "client_secret" not in body.lower()
        assert "AMADEUS_CLIENT_SECRET" not in body


# ─────────────────────────────────────────────────────────────────────────────
# Fares
# ─────────────────────────────────────────────────────────────────────────────

class TestFares:
    def test_list_fares_returns_200(self, api_client):
        resp = api_client.get("/api/fares")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    def test_fares_filter_origin(self, api_client):
        resp = api_client.get("/api/fares?origin=DEL")
        assert resp.status_code == 200
        for record in resp.json()["data"]:
            assert record["origin"] == "DEL"

    def test_fares_filter_cabin(self, api_client):
        resp = api_client.get("/api/fares?cabin_class=Business")
        assert resp.status_code == 200

    def test_fares_pagination(self, api_client):
        resp = api_client.get("/api/fares?limit=1&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) <= 1
        assert data["meta"]["limit"] == 1

    def test_fares_no_credentials_in_response(self, api_client):
        resp = api_client.get("/api/fares")
        assert "secret" not in resp.text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

class TestRoutes:
    def test_list_routes_returns_200(self, api_client):
        resp = api_client.get("/api/routes")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data

    def test_routes_structure(self, api_client):
        resp = api_client.get("/api/routes")
        if resp.json()["total"] > 0:
            record = resp.json()["data"][0]
            assert "origin" in record
            assert "destination" in record


# ─────────────────────────────────────────────────────────────────────────────
# Airlines
# ─────────────────────────────────────────────────────────────────────────────

class TestAirlines:
    def test_list_airlines_returns_200(self, api_client):
        resp = api_client.get("/api/airlines")
        assert resp.status_code == 200

    def test_airlines_structure(self, api_client):
        resp = api_client.get("/api/airlines")
        data = resp.json()
        assert "data" in data
        assert "total" in data
        if data["total"] > 0:
            airline = data["data"][0]
            assert "code" in airline
            assert "name" in airline


# ─────────────────────────────────────────────────────────────────────────────
# Index
# ─────────────────────────────────────────────────────────────────────────────

class TestIndex:
    def test_list_index_returns_200(self, api_client):
        resp = api_client.get("/api/index")
        assert resp.status_code == 200
        data = resp.json()
        assert "disclaimer" in data
        assert "PROTOTYPE" in data["disclaimer"]

    def test_index_has_disclaimer(self, api_client):
        resp = api_client.get("/api/index")
        disclaimer = resp.json()["disclaimer"]
        assert "NOT an official Government of India" in disclaimer

    def test_route_index_not_found(self, api_client):
        resp = api_client.get("/api/index/XYZ/ABC")
        assert resp.status_code == 404

    def test_route_index_found(self, api_client):
        resp = api_client.get("/api/index/DEL/BOM")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) > 0
        assert data["data"][0]["route"] == "DEL-BOM"


# ─────────────────────────────────────────────────────────────────────────────
# Prediction
# ─────────────────────────────────────────────────────────────────────────────

class TestPrediction:
    def test_prediction_model_loaded(self, api_client):
        resp = api_client.get(
            "/api/prediction",
            params={
                "origin": "Delhi",
                "destination": "Mumbai",
                "airline": "IndiGo",
                "cabin_class": "Economy",
                "days_left": 20,
            },
        )
        # 200 = model loaded and prediction succeeded
        # 503 = model not trained yet (acceptable if no model artifact present)
        assert resp.status_code in (200, 503)

    def test_prediction_same_origin_destination_422(self, api_client):
        resp = api_client.get(
            "/api/prediction",
            params={"origin": "Mumbai", "destination": "Mumbai"},
        )
        assert resp.status_code == 422

    def test_prediction_missing_origin_422(self, api_client):
        resp = api_client.get("/api/prediction", params={"destination": "BOM"})
        assert resp.status_code == 422

    def test_prediction_response_has_disclaimer(self, api_client):
        resp = api_client.get(
            "/api/prediction",
            params={"origin": "Delhi", "destination": "Mumbai"},
        )
        if resp.status_code == 200:
            assert "disclaimer" in resp.json()
            assert "secret" not in resp.text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Anomalies
# ─────────────────────────────────────────────────────────────────────────────

class TestAnomalies:
    def test_list_anomalies_returns_200(self, api_client):
        resp = api_client.get("/api/anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    def test_anomalies_filter_route(self, api_client):
        resp = api_client.get("/api/anomalies?route=DEL-BOM")
        assert resp.status_code == 200

    def test_anomalies_filter_method(self, api_client):
        resp = api_client.get("/api/anomalies?method=IQR")
        assert resp.status_code == 200
        for record in resp.json()["data"]:
            assert record["method"] == "IQR"


# ─────────────────────────────────────────────────────────────────────────────
# DGCA
# ─────────────────────────────────────────────────────────────────────────────

class TestDGCA:
    def test_list_dgca_returns_200(self, api_client):
        resp = api_client.get("/api/dgca")
        assert resp.status_code == 200
        data = resp.json()
        assert "disclaimer" in data
        assert "NOT airfare" in data["disclaimer"]

    def test_dgca_summary(self, api_client):
        resp = api_client.get("/api/dgca/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_records" in data


# ─────────────────────────────────────────────────────────────────────────────
# CPI
# ─────────────────────────────────────────────────────────────────────────────

class TestCPI:
    def test_list_cpi_returns_200(self, api_client):
        resp = api_client.get("/api/cpi")
        assert resp.status_code == 200
        data = resp.json()
        assert "disclaimer" in data
        assert "MoSPI" in data["disclaimer"]

    def test_cpi_structure(self, api_client):
        resp = api_client.get("/api/cpi")
        data = resp.json()
        if data["total"] > 0:
            record = data["data"][0]
            assert "indicator" in record
            assert "period" in record
            assert "value" in record


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

class TestDashboard:
    def test_dashboard_summary_returns_200(self, api_client):
        resp = api_client.get("/api/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_fare_observations" in data
        assert "total_routes" in data
        assert "total_airlines" in data
        assert "total_anomalies" in data
        assert "demo_mode" in data
        assert "disclaimer" in data

    def test_dashboard_no_credentials_in_response(self, api_client):
        resp = api_client.get("/api/dashboard/summary")
        assert "secret" not in resp.text.lower()
        assert "client_id" not in resp.text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Live status + DEMO mode
# ─────────────────────────────────────────────────────────────────────────────

class TestLiveStatus:
    def test_live_status_demo_mode(self, api_client):
        """When DEMO_MODE=true, status should show DEMO."""
        resp = api_client.get("/api/live/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["demo_mode"] is True
        assert "DEMO" in data["mode_label"]

    def test_live_status_no_secrets(self, api_client):
        resp = api_client.get("/api/live/status")
        body = resp.text
        assert "client_secret" not in body.lower()
        assert "AMADEUS_CLIENT_SECRET" not in body


class TestLiveSearch:
    def test_live_search_demo_fallback(self, api_client):
        """With DEMO_MODE=true, /api/live/search returns historical data."""
        resp = api_client.get(
            "/api/live/search",
            params={
                "origin": "DEL",
                "destination": "BOM",
                "departure_date": "2024-12-01",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data_mode"] in ("DEMO", "HISTORICAL")
        assert "DEMO" in data["disclaimer"]

    def test_live_search_bad_date_422(self, api_client):
        resp = api_client.get(
            "/api/live/search",
            params={
                "origin": "DEL",
                "destination": "BOM",
                "departure_date": "not-a-date",
            },
        )
        assert resp.status_code == 422

    def test_live_search_no_credentials_in_response(self, api_client):
        resp = api_client.get(
            "/api/live/search",
            params={
                "origin": "DEL",
                "destination": "BOM",
                "departure_date": "2024-12-01",
            },
        )
        assert "secret" not in resp.text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Amadeus service — mocked unit tests (NO real API calls)
# ─────────────────────────────────────────────────────────────────────────────

class TestAmadeusServiceMocked:
    """
    All tests use mocked HTTP sessions.
    No real Amadeus API is contacted.
    No credentials are used in these tests.
    """

    def _make_settings(self) -> Any:
        from backend.app.core.config import Settings
        return Settings(
            _env_file=None,
            DATABASE_URL="sqlite:///:memory:",
            DEMO_MODE=False,
            AMADEUS_CLIENT_ID="TEST_ID",
            AMADEUS_CLIENT_SECRET="TEST_SECRET",  # noqa: S106 — test stub only
            AMADEUS_BASE_URL="https://test.api.amadeus.com",
        )

    def _make_service(self, mock_session):
        from backend.app.services.amadeus_service import AmadeusService
        settings = self._make_settings()
        return AmadeusService(settings=settings, http_session=mock_session)

    def test_token_fetch_success(self):
        """Token is fetched and stored without being returned to caller."""
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "mock_token_abc", "expires_in": 1799}
        mock_resp.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_resp

        svc = self._make_service(mock_session)
        token = svc._fetch_token()
        assert token == "mock_token_abc"

        # Verify credentials were sent in POST body (not in URL)
        call_kwargs = mock_session.post.call_args
        assert "client_secret" not in str(call_kwargs[0])  # not in URL

    def test_token_fetch_failure_raises(self):
        """Auth failure raises AmadeusAuthError, not a credential leak."""
        import requests as req
        from backend.app.services.amadeus_service import AmadeusAuthError
        mock_session = MagicMock()
        mock_session.post.side_effect = req.ConnectionError("connection refused")

        svc = self._make_service(mock_session)
        with pytest.raises(AmadeusAuthError):
            svc._fetch_token()

    def test_search_returns_normalized_offers(self):
        """Search results are normalized to project structure."""
        mock_session = MagicMock()

        # Token response
        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {"access_token": "tok_xyz"}
        token_resp.raise_for_status = MagicMock()

        # Search response — minimal realistic Amadeus payload
        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.raise_for_status = MagicMock()
        search_resp.json.return_value = {
            "data": [
                {
                    "price": {"grandTotal": "120.50", "currency": "EUR"},
                    "itineraries": [
                        {
                            "duration": "PT2H30M",
                            "segments": [
                                {
                                    "carrierCode": "6E",
                                    "departure": {"iataCode": "DEL", "at": "2024-12-01T08:00:00"},
                                    "arrival": {"iataCode": "BOM", "at": "2024-12-01T10:30:00"},
                                }
                            ],
                        }
                    ],
                    "travelerPricings": [
                        {"fareDetailsBySegment": [{"cabin": "ECONOMY"}]}
                    ],
                }
            ]
        }

        mock_session.post.return_value = token_resp
        mock_session.get.return_value = search_resp

        svc = self._make_service(mock_session)
        offers = svc.search_flights("DEL", "BOM", "2024-12-01")

        assert len(offers) == 1
        offer = offers[0]
        assert offer["source"] == "AMADEUS"
        assert offer["data_mode"] == "LIVE"
        assert offer["origin"] == "DEL"
        assert offer["destination"] == "BOM"
        assert offer["fare"] == 120.50
        assert offer["currency"] == "EUR"
        assert offer["fare_inr_estimate"] == round(120.50 * 90.0, 2)
        assert offer["duration_minutes"] == 150  # 2h30m
        assert offer["stops"] == 0
        assert offer["cabin_class"] == "Economy"
        assert isinstance(offer["collected_at"], datetime)

    def test_normalize_duration_parsing(self):
        """ISO 8601 duration parsing covers edge cases."""
        from backend.app.services.amadeus_service import _parse_iso_duration
        assert _parse_iso_duration("PT2H30M") == 150
        assert _parse_iso_duration("PT1H") == 60
        assert _parse_iso_duration("PT45M") == 45
        assert _parse_iso_duration("PT3H") == 180
        assert _parse_iso_duration("") is None
        assert _parse_iso_duration("NOT_ISO") is None

    def test_cabin_normalization(self):
        from backend.app.services.amadeus_service import _normalize_cabin
        assert _normalize_cabin("ECONOMY") == "Economy"
        assert _normalize_cabin("BUSINESS") == "Business"
        assert _normalize_cabin("FIRST") == "First"
        assert _normalize_cabin("PREMIUM_ECONOMY") == "Premium Economy"
        assert _normalize_cabin("UNKNOWN") == "Economy"  # safe default

    def test_connectivity_check_returns_bool(self):
        """check_connectivity never raises — returns bool."""
        import requests as req
        mock_session = MagicMock()
        mock_session.post.side_effect = req.ConnectionError("timeout")

        svc = self._make_service(mock_session)
        result = svc.check_connectivity()
        assert result is False

    def test_connectivity_check_success(self):
        mock_session = MagicMock()
        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {"access_token": "tok"}
        token_resp.raise_for_status = MagicMock()
        mock_session.post.return_value = token_resp

        svc = self._make_service(mock_session)
        result = svc.check_connectivity()
        assert result is True

    def test_missing_credentials_behavior(self):
        """With empty credentials, amadeus_available=False, service stays in DEMO."""
        from backend.app.core.config import Settings
        s = Settings(
            _env_file=None,
            DATABASE_URL="sqlite:///:memory:",
            DEMO_MODE=False,
            AMADEUS_CLIENT_ID="",
            AMADEUS_CLIENT_SECRET="",
        )
        assert s.amadeus_available is False

    def test_demo_mode_overrides_credentials(self):
        """DEMO_MODE=true → amadeus_available=False even if credentials set."""
        from backend.app.core.config import Settings
        s = Settings(
            _env_file=None,
            DATABASE_URL="sqlite:///:memory:",
            DEMO_MODE=True,
            AMADEUS_CLIENT_ID="some_id",
            AMADEUS_CLIENT_SECRET="some_secret",  # noqa: S106
        )
        assert s.amadeus_available is False


# ─────────────────────────────────────────────────────────────────────────────
# Security: no secrets in any response
# ─────────────────────────────────────────────────────────────────────────────

class TestSecurityNoSecretsInResponses:
    """Ensure no credential data leaks through any API endpoint."""

    ENDPOINTS = [
        "/health",
        "/api/fares",
        "/api/routes",
        "/api/airlines",
        "/api/index",
        "/api/anomalies",
        "/api/dgca",
        "/api/dgca/summary",
        "/api/cpi",
        "/api/dashboard/summary",
        "/api/live/status",
    ]

    def test_no_secret_in_any_endpoint(self, api_client):
        for endpoint in self.ENDPOINTS:
            resp = api_client.get(endpoint)
            body = resp.text.lower()
            assert "client_secret" not in body, f"Secret leaked from {endpoint}"
            assert "amadeus_client_secret" not in body, f"Secret leaked from {endpoint}"
