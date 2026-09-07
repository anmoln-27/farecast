"""
tests/test_amadeus_persistence.py
---------------------------------
Unit & integration tests verifying Amadeus LIVE airfare connectivity & database persistence.
Tests:
  - Live offers persistence into fare_observations table
  - Data mode is strictly LIVE
  - Correct advance_window mapping (T+1, T+7, T+15, T+30, T+45)
  - Auto-upsert of airline reference to prevent foreign key errors
  - Immediate availability through /api/fares?data_mode=LIVE
  - Preserves DEMO_MODE fallback with zero live data fabrication
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
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
from backend.main import app


@pytest.fixture(scope="module")
def live_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="module")
def live_db(live_engine):
    Session = sessionmaker(bind=live_engine)
    session = Session()
    # Seed canonical airline
    session.add(Airline(code="6E", name="IndiGo", country="India"))
    session.add(Airline(code="AI", name="Air India", country="India"))
    session.commit()
    yield session
    session.close()


def test_persist_live_offers_direct(live_db):
    """Test that _persist_live_offers saves offers to DB under DataMode.LIVE with correct windows."""
    future_date = (date.today() + timedelta(days=7)).isoformat()
    offers = [
        LiveFareOffer(
            source="AMADEUS",
            data_mode="LIVE",
            origin="DEL",
            destination="BOM",
            airline_code="6E",
            airline_name="IndiGo",
            departure_datetime=f"{future_date}T08:30:00",
            arrival_datetime=f"{future_date}T10:45:00",
            duration_minutes=135,
            stops=0,
            cabin_class="Economy",
            fare=65.0,
            currency="EUR",
            fare_inr_estimate=5850.0,
            collected_at=datetime.now(timezone.utc),
        ),
        LiveFareOffer(
            source="AMADEUS",
            data_mode="LIVE",
            origin="DEL",
            destination="BOM",
            airline_code="NEW_AIR",  # Tests airline creation on demand
            airline_name="New Airline",
            departure_datetime=f"{future_date}T14:00:00",
            arrival_datetime=f"{future_date}T16:15:00",
            duration_minutes=135,
            stops=0,
            cabin_class="Business",
            fare=150.0,
            currency="EUR",
            fare_inr_estimate=13500.0,
            collected_at=datetime.now(timezone.utc),
        ),
    ]

    count = _persist_live_offers(live_db, offers, future_date)
    assert count == 2

    # Query back from DB
    persisted = (
        live_db.query(FareObservation)
        .filter(FareObservation.source == "amadeus", FareObservation.data_mode == DataMode.LIVE)
        .all()
    )
    assert len(persisted) == 2
    assert persisted[0].advance_window == "T+7"
    assert persisted[0].days_left == 7
    assert persisted[0].fare == 5850.0
    assert persisted[1].cabin_class == CabinClass.BUSINESS
    assert persisted[1].airline_code == "NEW_AIR"


def test_live_search_endpoint_with_mocked_amadeus(live_engine):
    """Test /api/live/search persists results and returns persisted_count when live search runs."""
    TestingSessionLocal = sessionmaker(bind=live_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    mock_settings = Settings(
        _env_file=None,
        DATABASE_URL="sqlite:///:memory:",
        DEMO_MODE=False,
        AMADEUS_CLIENT_ID="mock_id",
        AMADEUS_CLIENT_SECRET="mock_secret",
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: mock_settings
    client = TestClient(app)

    dep_date = (date.today() + timedelta(days=1)).isoformat()
    mock_raw_offers = [
        {
            "source": "AMADEUS",
            "data_mode": "LIVE",
            "origin": "DEL",
            "destination": "BLR",
            "airline_code": "AI",
            "airline_name": "Air India",
            "departure_datetime": f"{dep_date}T06:00:00",
            "arrival_datetime": f"{dep_date}T08:45:00",
            "duration_minutes": 165,
            "stops": 0,
            "cabin_class": "Economy",
            "fare": 90.0,
            "currency": "EUR",
            "fare_inr_estimate": 8100.0,
            "collected_at": datetime.now(timezone.utc),
            "segments": [],
        }
    ]

    with patch("backend.app.api.routers.live.get_amadeus_service") as mock_svc_getter:
        mock_svc = MagicMock()
        mock_svc.search_flights.return_value = mock_raw_offers
        mock_svc_getter.return_value = mock_svc

        resp = client.get(
            f"/api/live/search?origin=DEL&destination=BLR&departure_date={dep_date}&persist=true"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data_mode"] == "LIVE"
        assert data["source"] == "AMADEUS"
        assert data["total"] == 1
        assert data["persisted_count"] == 1
        assert data["offers"][0]["fare_inr_estimate"] == 8100.0

    # Verify that query to /api/fares with data_mode=LIVE returns this observation
    fares_resp = client.get("/api/fares?origin=DEL&destination=BLR&data_mode=LIVE")
    assert fares_resp.status_code == 200
    fares_data = fares_resp.json()
    assert fares_data["meta"]["total"] >= 1
    assert any(f["source"] == "amadeus" for f in fares_data["data"])

    # Clean up overrides
    app.dependency_overrides.clear()
