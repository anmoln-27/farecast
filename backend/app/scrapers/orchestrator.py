"""
backend/app/scrapers/orchestrator.py
------------------------------------
Multi-Source Scraper Orchestrator.
Coordinates scheduled and on-demand sweeps across Indian airline routes
and the 5 mandatory advance-purchase windows (T+1, T+7, T+15, T+30, T+45).
Cleans and normalises observations, then persists them to the database.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from backend.app.db.base import SessionLocal
from backend.app.db.models import DataMode, FareObservation
from backend.app.scrapers.airline_scrapers import (
    AirIndiaExpressScraper,
    AirIndiaScraper,
    AkasaAirScraper,
    IndiGoScraper,
    OTAScraper,
    SpiceJetScraper,
)
from backend.app.services.cleaner import clean_fare_records, detect_route_window_outliers
from backend.app.services.schema import FareRecord

logger = logging.getLogger(__name__)

# Canonical domestic route basket covering >65% of Indian domestic passenger traffic
CANONICAL_ROUTES: list[tuple[str, str]] = [
    ("DEL", "BOM"),
    ("DEL", "BLR"),
    ("BOM", "BLR"),
    ("DEL", "CCU"),
    ("BLR", "HYD"),
    ("MAA", "DEL"),
    ("BOM", "GOI"),
    ("DEL", "PNQ"),
]

# Mandatory advance-purchase observation windows
MANDATORY_WINDOWS: dict[str, int] = {
    "T+1": 1,
    "T+7": 7,
    "T+15": 15,
    "T+30": 30,
    "T+45": 45,
}


class ScraperOrchestrator:
    """
    Coordinates multi-source data ingestion across airline scrapers.
    """

    def __init__(self, delay_between_routes: float = 0.5):
        self.delay_between_routes = delay_between_routes
        self.scrapers = [
            IndiGoScraper(),
            AirIndiaScraper(),
            AirIndiaExpressScraper(),
            AkasaAirScraper(),
            SpiceJetScraper(),
            OTAScraper(),
        ]

    def run_sweep(
        self,
        routes: Optional[list[tuple[str, str]]] = None,
        windows: Optional[dict[str, int]] = None,
        simulate: bool = True,
        save_to_db: bool = True,
    ) -> dict:
        """
        Execute an ingestion sweep across specified routes and advance windows.

        Returns:
            dict containing raw_count, cleaned_count, saved_count, and cleaning report.
        """
        target_routes = routes or CANONICAL_ROUTES
        target_windows = windows or MANDATORY_WINDOWS
        today = date.today()

        raw_records: list[FareRecord] = []
        logger.info(
            "Starting scraper sweep | %d routes | %d windows | %d scrapers | simulate=%s",
            len(target_routes),
            len(target_windows),
            len(self.scrapers),
            simulate,
        )

        for orig, dest in target_routes:
            for win_label, days_ahead in target_windows.items():
                target_date = today + timedelta(days=days_ahead)
                for scraper in self.scrapers:
                    try:
                        fares = scraper.search_fares(
                            origin=orig,
                            destination=dest,
                            travel_date=target_date,
                            advance_window=win_label,
                            simulate=simulate,
                        )
                        raw_records.extend(fares)
                    except Exception as exc:
                        logger.error(
                            "Error scraping [%s] %s->%s (%s): %s",
                            scraper.airline_code,
                            orig,
                            dest,
                            win_label,
                            exc,
                        )

        logger.info("Scraper sweep complete. Collected %d raw observations.", len(raw_records))

        # Data Cleaning and validation
        cleaned_records, report = clean_fare_records(raw_records, source="scraper_sweep")
        filtered_records = detect_route_window_outliers(cleaned_records)

        saved_count = 0
        if save_to_db and filtered_records:
            saved_count = self._persist_records(filtered_records)

        return {
            "status": "success",
            "raw_count": len(raw_records),
            "cleaned_count": len(filtered_records),
            "saved_count": saved_count,
            "routes_swept": len(target_routes),
            "windows_swept": list(target_windows.keys()),
            "cleaning_report": report.summary(),
        }

    def _persist_records(self, records: list[FareRecord]) -> int:
        """Persist cleaned FareRecords to the fare_observations table."""
        session_factory = SessionLocal()
        session = session_factory()
        saved = 0
        try:
            for rec in records:
                obs = FareObservation(
                    source=rec.source,
                    data_mode=DataMode(rec.data_mode) if getattr(rec, "data_mode", None) in DataMode.__members__.values() else DataMode.DEMO,
                    airline_code=rec.airline_code,
                    flight_number=rec.flight_number,
                    origin=rec.origin,
                    destination=rec.destination,
                    travel_date=rec.travel_date,
                    booking_date=rec.booking_date,
                    departure_time=rec.departure_time,
                    arrival_time=rec.arrival_time,
                    stops=rec.stops,
                    duration_minutes=rec.duration_minutes,
                    cabin_class=rec.cabin_class,
                    fare=rec.fare,
                    currency=rec.currency,
                    base_fare=rec.base_fare,
                    taxes=rec.taxes,
                    udf_charge=rec.udf_charge,
                    convenience_fee=rec.convenience_fee,
                    total_fare=rec.total_fare,
                    advance_window=rec.advance_window,
                    status=rec.status,
                    days_left=rec.days_left,
                    collected_at=rec.collected_at or datetime.utcnow(),
                )
                session.add(obs)
                saved += 1
            session.commit()
            logger.info("Persisted %d fare observations to database.", saved)
        except Exception as exc:
            session.rollback()
            logger.error("Failed to persist observations: %s", exc)
            raise
        finally:
            session.close()

        return saved
