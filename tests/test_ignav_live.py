"""
tests/test_ignav_live.py
------------------------
Mocked unit and integration tests for Ignav Live Airfare Provider.
Zero real network requests are made.

Tests cover:
  1. Missing IGNAV_API_KEY -> /health reports ignav_configured=False
  2. Configured IGNAV_API_KEY -> /health reports ignav_configured=True
  3. Successful Ignav response parsing (direct flight)
  4. Connecting flight parsing (stops = 1, combined times)
  5. Indian market parameter (market="IN", currency="INR")
  6. Database normalization & persistence into fare_observations (DataMode.LIVE, source="ignav")
  7. No synthetic fare breakdown invention (base_fare, taxes, etc. remain None)
  8. API failure / 500 / 503 handling -> safe fallback to DEMO mode
  9. Safe fallback guarantee: DEMO data is NEVER labelled LIVE
 10. Credentials security: API key never appears in logs, responses, or error details
 11. Provider hierarchy: Amadeus remains available when Ignav is unconfigured
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.deps import get_db, get_settings
from backend.app.api.routers.live import _persist_live_offers
from backend.app.core.config import Settings
from backend.app.db.base import Base
from backend.app.db.models import Airline, CabinClass, DataMode, FareObservation
from backend.app.schemas.responses import LiveFareOffer
from backend.app.services.ignav_service import IgnavService, get_ignav_service
from backend.main import app


@pytest.fixture(scope="module")
def mem_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def mem_db(mem_engine):
    Session = sessionmaker(bind=mem_engine)
    session = Session()
    # Ensure standard Indian airlines are seeded
    if not session.query(Airline).filter_by(code="6E").first():
        session.add(Airline(code="6E", name="IndiGo", country="India"))
    if not session.query(Airline).filter_by(code="AI").first():
        session.add(Airline(code="AI", name="Air India", country="India"))
    session.commit()
    yield session
    session.close()


# ─── 1. Health check & configuration detection ────────────────────────────────

def test_missing_ignav_api_key_health():
    """When IGNAV_API_KEY is empty, /health should report ignav_configured=False."""
    mock_settings = Settings(
        _env_file=None,
        IGNAV_API_KEY="",
        DEMO_MODE=True,
    )
    app.dependency_overrides[get_settings] = lambda: mock_settings
    client = TestClient(app)
    try:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ignav_configured"] is False
    finally:
        app.dependency_overrides.clear()


def test_configured_ignav_api_key_health():
    """When IGNAV_API_KEY is present, /health should report ignav_configured=True without leaking key."""
    secret_key = "ignav_test_mock_secret_999"
    mock_settings = Settings(
        _env_file=None,
        IGNAV_API_KEY=secret_key,
        DEMO_MODE=True,
    )
    app.dependency_overrides[get_settings] = lambda: mock_settings
    client = TestClient(app)
    try:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ignav_configured"] is True
        # Verify secret key is NOT in response body or headers
        assert secret_key not in resp.text
    finally:
        app.dependency_overrides.clear()


# ─── 2. Search endpoint: No API key -> Safe DEMO Fallback ─────────────────────

def test_no_api_key_safe_demo_fallback(mem_engine):
    """When no live provider is configured, search falls back to DEMO and is NEVER labelled LIVE."""
    TestingSession = sessionmaker(bind=mem_engine)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    mock_settings = Settings(
        _env_file=None,
        IGNAV_API_KEY="",
        AMADEUS_CLIENT_ID="",
        AMADEUS_CLIENT_SECRET="",
        DEMO_MODE=True,
    )
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: mock_settings
    client = TestClient(app)
    try:
        resp = client.get("/api/live/search?origin=DEL&destination=BOM&departure_date=2026-10-15")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data_mode"] != "LIVE"
        assert data["data_mode"] in ("DEMO", "HISTORICAL")
        assert data["source"] == "HISTORICAL"
        for offer in data["offers"]:
            assert offer["data_mode"] != "LIVE"
    finally:
        app.dependency_overrides.clear()


# ─── 3. Ignav Service Direct Flight Parsing & Market=IN ───────────────────────

def test_ignav_service_direct_flight_parsing():
    """Test IgnavService parsing a mock direct flight response with INR currency and Indian market."""
    mock_settings = Settings(
        _env_file=None,
        IGNAV_API_KEY="mock_key_test_123",
        IGNAV_BASE_URL="https://ignav.com",
    )
    mock_response_data = {
        "origin": "DEL",
        "destination": "BOM",
        "departure_date": "2026-10-15",
        "itineraries": [
          {
            "price": {
              "amount": 4350.0,
              "currency": "INR",
              "status": "verified"
            },
            "outbound": {
              "carrier": "6E",
              "duration_minutes": 130,
              "segments": [
                {
                  "marketing_carrier_code": "6E",
                  "flight_number": "501",
                  "operating_carrier_name": "IndiGo",
                  "departure_airport": "DEL",
                  "departure_time_local": "2026-10-15T07:00:00",
                  "departure_timezone": "Asia/Kolkata",
                  "departure_time_utc": "2026-10-15T01:30:00Z",
                  "arrival_airport": "BOM",
                  "arrival_time_local": "2026-10-15T09:10:00",
                  "arrival_timezone": "Asia/Kolkata",
                  "arrival_time_utc": "2026-10-15T03:40:00Z",
                  "duration_minutes": 130,
                  "aircraft": "A321"
                }
              ]
            },
            "cabin_class": "economy",
            "ignav_id": "ignav_test_offer_1"
          }
        ]
    }

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response_data
    mock_session.post.return_value = mock_resp

    svc = IgnavService(mock_settings, http_session=mock_session)
    results = svc.search_flights(
        origin="DEL",
        destination="BOM",
        departure_date="2026-10-15",
        adults=1,
        travel_class="ECONOMY",
        market="IN",
    )

    # Verify request payload to Ignav API
    mock_session.post.assert_called_once()
    call_kwargs = mock_session.post.call_args[1]
    assert call_kwargs["json"]["origin"] == "DEL"
    assert call_kwargs["json"]["destination"] == "BOM"
    assert call_kwargs["json"]["market"] == "IN"
    assert call_kwargs["json"]["cabin_class"] == "economy"
    assert "X-Api-Key" in call_kwargs["headers"]

    # Verify parsed normalized structure
    assert len(results) == 1
    item = results[0]
    assert item["source"] == "IGNAV"
    assert item["data_mode"] == "LIVE"
    assert item["origin"] == "DEL"
    assert item["destination"] == "BOM"
    assert item["airline_code"] == "6E"
    assert item["airline_name"] == "IndiGo"
    assert item["flight_number"] == "6E-501"
    assert item["stops"] == 0
    assert item["duration_minutes"] == 130
    assert item["fare"] == 4350.0
    assert item["currency"] == "INR"
    assert item["fare_inr_estimate"] == 4350.0
    assert item["departure_datetime"] == "2026-10-15T07:00:00"
    assert item["arrival_datetime"] == "2026-10-15T09:10:00"


# ─── 4. Connecting Flight Parsing (1 Stop) ────────────────────────────────────

def test_ignav_service_connecting_flight_parsing():
    """Test connecting flight parsing: stops calculated as len(segments) - 1, proper start/end datetimes."""
    mock_settings = Settings(
        _env_file=None,
        IGNAV_API_KEY="mock_key_test_123",
    )
    mock_response_data = {
        "origin": "DEL",
        "destination": "BLR",
        "departure_date": "2026-10-20",
        "itineraries": [
          {
            "price": {
              "amount": 5600.0,
              "currency": "INR",
              "status": "verified"
            },
            "outbound": {
              "carrier": "AI",
              "duration_minutes": 270,
              "segments": [
                {
                  "marketing_carrier_code": "AI",
                  "flight_number": "AI-801",
                  "operating_carrier_name": "Air India",
                  "departure_airport": "DEL",
                  "departure_time_local": "2026-10-20T06:00:00",
                  "departure_timezone": "Asia/Kolkata",
                  "departure_time_utc": "2026-10-20T00:30:00Z",
                  "arrival_airport": "HYD",
                  "arrival_time_local": "2026-10-20T08:15:00",
                  "arrival_timezone": "Asia/Kolkata",
                  "arrival_time_utc": "2026-10-20T02:45:00Z",
                  "duration_minutes": 135,
                  "aircraft": "A320"
                },
                {
                  "marketing_carrier_code": "AI",
                  "flight_number": "AI-543",
                  "operating_carrier_name": "Air India",
                  "departure_airport": "HYD",
                  "departure_time_local": "2026-10-20T09:30:00",
                  "departure_timezone": "Asia/Kolkata",
                  "departure_time_utc": "2026-10-20T04:00:00Z",
                  "arrival_airport": "BLR",
                  "arrival_time_local": "2026-10-20T10:30:00",
                  "arrival_timezone": "Asia/Kolkata",
                  "arrival_time_utc": "2026-10-20T05:00:00Z",
                  "duration_minutes": 60,
                  "aircraft": "A320"
                }
              ]
            },
            "cabin_class": "economy",
            "ignav_id": "ignav_test_connecting"
          }
        ]
    }

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response_data
    mock_session.post.return_value = mock_resp

    svc = IgnavService(mock_settings, http_session=mock_session)
    results = svc.search_flights("DEL", "BLR", "2026-10-20")

    assert len(results) == 1
    item = results[0]
    assert item["stops"] == 1
    assert item["departure_datetime"] == "2026-10-20T06:00:00"
    assert item["arrival_datetime"] == "2026-10-20T10:30:00"
    assert item["duration_minutes"] == 270


# ─── 5. Normalization & Persistence into fare_observations ────────────────────

def test_ignav_persistence_to_database(mem_db):
    """Test that live Ignav offers persist with source='ignav', DataMode.LIVE, and NO invented fare breakdowns."""
    future_date = (date.today() + timedelta(days=7)).isoformat()
    offers = [
        LiveFareOffer(
            source="IGNAV",
            data_mode="LIVE",
            origin="DEL",
            destination="BOM",
            airline_code="6E",
            airline_name="IndiGo",
            flight_number="6E-204",
            departure_datetime=f"{future_date}T08:00:00",
            arrival_datetime=f"{future_date}T10:15:00",
            duration_minutes=135,
            stops=0,
            cabin_class="Economy",
            fare=4500.0,
            currency="INR",
            fare_inr_estimate=4500.0,
            collected_at=datetime.now(timezone.utc),
        )
    ]

    persisted_count = _persist_live_offers(mem_db, offers, future_date, source="ignav")
    assert persisted_count == 1

    saved = (
        mem_db.query(FareObservation)
        .filter(FareObservation.source == "ignav", FareObservation.data_mode == DataMode.LIVE)
        .first()
    )
    assert saved is not None
    assert saved.origin == "DEL"
    assert saved.destination == "BOM"
    assert saved.flight_number == "6E-204"
    assert saved.fare == 4500.0
    assert saved.total_fare == 4500.0
    assert saved.currency == "INR"
    assert saved.advance_window == "T+7"
    assert saved.stops == 0

    # Guarantee: Do NOT invent missing fare components
    assert saved.base_fare is None
    assert saved.taxes is None
    assert saved.udf_charge is None
    assert saved.convenience_fee is None


# ─── 6. Live Endpoint Integration with Mocked Ignav ───────────────────────────

def test_live_search_endpoint_with_mocked_ignav(mem_engine):
    """Test /api/live/search invokes Ignav when configured and returns properly tagged LIVE results."""
    TestingSession = sessionmaker(bind=mem_engine)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    mock_settings = Settings(
        _env_file=None,
        IGNAV_API_KEY="mock_ignav_key_active",
        DEMO_MODE=True,  # DEMO_MODE=True globally must NOT block Ignav when key is configured
    )
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: mock_settings
    client = TestClient(app)

    dep_date = (date.today() + timedelta(days=7)).isoformat()
    mock_offers = [
        {
            "source": "IGNAV",
            "data_mode": "LIVE",
            "origin": "DEL",
            "destination": "BOM",
            "airline_code": "6E",
            "airline_name": "IndiGo",
            "flight_number": "6E-204",
            "departure_datetime": f"{dep_date}T09:00:00",
            "arrival_datetime": f"{dep_date}T11:15:00",
            "duration_minutes": 135,
            "stops": 0,
            "cabin_class": "Economy",
            "fare": 4800.0,
            "currency": "INR",
            "fare_inr_estimate": 4800.0,
            "collected_at": datetime.now(timezone.utc),
            "segments": [],
        }
    ]

    with patch("backend.app.api.routers.live.get_ignav_service") as mock_getter:
        mock_svc = MagicMock()
        mock_svc.search_flights.return_value = mock_offers
        mock_getter.return_value = mock_svc

        resp = client.get(
            f"/api/live/search?origin=DEL&destination=BOM&departure_date={dep_date}&persist=true"
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["data_mode"] == "LIVE"
        assert data["source"] == "IGNAV"
        assert data["total"] == 1
        assert data["persisted_count"] == 1
        assert data["offers"][0]["fare"] == 4800.0
        assert data["offers"][0]["currency"] == "INR"
        assert data["offers"][0]["flight_number"] == "6E-204"

    app.dependency_overrides.clear()


# ─── 7. API Failure Handling & Fallback Guarantee ─────────────────────────────

def test_ignav_api_error_fallback_never_labelled_live(mem_engine):
    """When Ignav fails (e.g. 500/503), it safely falls back to DEMO and is NEVER labelled LIVE."""
    TestingSession = sessionmaker(bind=mem_engine)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    mock_settings = Settings(
        _env_file=None,
        IGNAV_API_KEY="mock_ignav_key_failing",
        DEMO_MODE=True,
    )
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: mock_settings
    client = TestClient(app)

    with patch("backend.app.api.routers.live.get_ignav_service") as mock_getter:
        mock_svc = MagicMock()
        mock_svc.search_flights.side_effect = requests.RequestException("Ignav 503 Service Unavailable")
        mock_getter.return_value = mock_svc

        resp = client.get("/api/live/search?origin=DEL&destination=BOM&departure_date=2026-10-15")
        assert resp.status_code == 200
        data = resp.json()

        # MUST fall back to DEMO / HISTORICAL and NEVER claim to be LIVE
        assert data["data_mode"] != "LIVE"
        assert data["data_mode"] in ("DEMO", "HISTORICAL")
        assert data["source"] == "HISTORICAL"

    app.dependency_overrides.clear()


# ─── 8. API Key Security & Redaction ──────────────────────────────────────────

def test_api_key_never_appears_in_logs_or_errors(caplog):
    """Verify that the raw IGNAV_API_KEY never leaks into logs, exceptions, or responses."""
    secret_key = "super_confidential_ignav_token_xyz888"
    mock_settings = Settings(
        _env_file=None,
        IGNAV_API_KEY=secret_key,
        IGNAV_BASE_URL="https://ignav.com",
    )

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"
    mock_session.post.return_value = mock_resp

    svc = IgnavService(mock_settings, http_session=mock_session)

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(Exception) as exc_info:
            svc.search_flights("DEL", "BOM", "2026-10-15")

        # Key must not appear in exception message
        assert secret_key not in str(exc_info.value)

    # Key must not appear in any captured log message
    for record in caplog.records:
        assert secret_key not in record.message


# ─── 9. Amadeus Alternative Provider Preservation ─────────────────────────────

def test_amadeus_remains_available_when_ignav_not_configured():
    """Verify Amadeus is selected when IGNAV_API_KEY is unset and Amadeus credentials exist with DEMO_MODE=False."""
    mock_settings = Settings(
        _env_file=None,
        IGNAV_API_KEY="",
        AMADEUS_CLIENT_ID="amadeus_client_id",
        AMADEUS_CLIENT_SECRET="amadeus_secret",
        DEMO_MODE=False,
    )
    assert mock_settings.ignav_available is False
    assert mock_settings.amadeus_available is True

    app.dependency_overrides[get_settings] = lambda: mock_settings
    client = TestClient(app)

    with patch("backend.app.api.routers.live.get_amadeus_service") as mock_amadeus_getter:
        mock_svc = MagicMock()
        mock_svc.search_flights.return_value = []
        mock_amadeus_getter.return_value = mock_svc

        resp = client.get("/api/live/search?origin=DEL&destination=BOM&departure_date=2026-10-15")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "AMADEUS"
        assert data["data_mode"] == "LIVE"

    app.dependency_overrides.clear()
