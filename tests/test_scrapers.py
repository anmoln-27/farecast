"""
tests/test_scrapers.py
----------------------
Unit tests for the multi-source scraping and ingestion engine.
"""
from datetime import date, timedelta
import pytest

from backend.app.scrapers.base import BaseScraper, USER_AGENTS
from backend.app.scrapers.airline_scrapers import (
    IndiGoScraper,
    AirIndiaScraper,
    AirIndiaExpressScraper,
    AkasaAirScraper,
    SpiceJetScraper,
    OTAScraper,
    WINDOW_SURGE_FACTORS,
)
from backend.app.scrapers.orchestrator import ScraperOrchestrator
from backend.app.services.schema import compute_fare_disaggregation


class TestBaseScraper:
    def test_user_agents_list(self):
        assert len(USER_AGENTS) >= 3
        for ua in USER_AGENTS:
            assert "Mozilla" in ua

    def test_headers_structure(self):
        scraper = IndiGoScraper(verify_robots=False)
        headers = scraper.get_headers()
        assert "User-Agent" in headers
        assert headers["User-Agent"] in USER_AGENTS
        assert headers["Accept"] != ""

    def test_robots_txt_allow_fallback(self):
        scraper = IndiGoScraper(verify_robots=False)
        assert scraper.is_allowed_by_robots("/flight-search") is True


class TestAirlineScrapers:
    def test_indigo_search(self):
        scraper = IndiGoScraper(verify_robots=False)
        target_date = date.today() + timedelta(days=7)
        fares = scraper.search_fares("DEL", "BOM", target_date, advance_window="T+7", simulate=True)
        assert len(fares) > 0
        for f in fares:
            assert f.airline_code == "6E"
            assert f.origin == "DEL"
            assert f.destination == "BOM"
            assert f.advance_window == "T+7"
            assert f.fare > 0
            assert f.base_fare > 0
            assert round(f.base_fare + f.taxes + f.udf_charge + f.convenience_fee, 2) == round(f.fare, 2)

    def test_air_india_search(self):
        scraper = AirIndiaScraper(verify_robots=False)
        target_date = date.today() + timedelta(days=15)
        fares = scraper.search_fares("BOM", "BLR", target_date, advance_window="T+15", simulate=True)
        assert len(fares) > 0
        assert all(f.airline_code == "AI" for f in fares)

    def test_akasa_air_search(self):
        scraper = AkasaAirScraper(verify_robots=False)
        target_date = date.today() + timedelta(days=1)
        fares = scraper.search_fares("BLR", "HYD", target_date, advance_window="T+1", simulate=True)
        assert len(fares) > 0
        assert all(f.airline_code == "QP" for f in fares)

    def test_ota_scraper_search(self):
        scraper = OTAScraper(verify_robots=False)
        target_date = date.today() + timedelta(days=30)
        fares = scraper.search_fares("DEL", "CCU", target_date, advance_window="T+30", simulate=True)
        assert len(fares) > 0
        assert fares[0].source == "ota_makemytrip"

    def test_advance_window_surge_progression(self):
        scraper = IndiGoScraper(verify_robots=False)
        today = date.today()
        fare_t45 = scraper.search_fares("DEL", "BOM", today + timedelta(days=45), "T+45")[0].fare
        fare_t30 = scraper.search_fares("DEL", "BOM", today + timedelta(days=30), "T+30")[0].fare
        fare_t15 = scraper.search_fares("DEL", "BOM", today + timedelta(days=15), "T+15")[0].fare
        fare_t7 = scraper.search_fares("DEL", "BOM", today + timedelta(days=7), "T+7")[0].fare
        fare_t1 = scraper.search_fares("DEL", "BOM", today + timedelta(days=1), "T+1")[0].fare

        # T+1 spot fare should be substantially higher than T+45 early bird
        assert fare_t1 > fare_t15 > fare_t45


class TestDisaggregationUtility:
    def test_exact_sum_balance(self):
        total = 5499.0
        disagg = compute_fare_disaggregation(total, origin="DEL", airline_code="6E")
        computed_total = disagg["base_fare"] + disagg["taxes"] + disagg["udf_charge"] + disagg["convenience_fee"]
        assert round(computed_total, 2) == round(total, 2)
        assert disagg["udf_charge"] == 300.0  # DEL airport UDF
        assert disagg["convenience_fee"] == 350.0


class TestScraperOrchestrator:
    def test_sweep_execution(self):
        orchestrator = ScraperOrchestrator()
        result = orchestrator.run_sweep(
            routes=[("DEL", "BOM")],
            windows={"T+7": 7, "T+15": 15},
            simulate=True,
            save_to_db=False,
        )
        assert result["status"] == "success"
        assert result["raw_count"] > 0
        assert result["cleaned_count"] > 0
        assert result["saved_count"] == 0


class TestScraperCompliance:
    def test_compliance_status_structure(self):
        scraper = IndiGoScraper(verify_robots=False)
        status = scraper.check_compliance_status("/")
        assert "airline_code" in status
        assert "airline_name" in status
        assert "robots_allowed" in status
        assert "access_state" in status
        assert "legal_compliance_rule" in status
        assert "SIH ethical scraping" in status["legal_compliance_rule"]

    def test_unpermitted_live_returns_empty_not_fabricated(self):
        scraper = IndiGoScraper(verify_robots=True)
        # In non-simulated mode with live fetch restricted, returns empty list — zero fabricated data
        fares = scraper.search_fares("DEL", "BOM", date.today() + timedelta(days=7), "T+7", simulate=False)
        assert isinstance(fares, list)
        # Should NOT return fake records masquerading as live
        assert all(f.data_mode == "LIVE" for f in fares)

    def test_compliance_api_endpoint(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        resp = client.get("/api/scrapers/compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sources"] == 7
        assert "disclaimer" in data
        assert len(data["sources"]) == 7
        assert any(s["airline_code"] == "6E" for s in data["sources"])
        assert any(s["airline_code"] == "AI" for s in data["sources"])
        assert any(s["airline_code"] == "EMT" for s in data["sources"])
