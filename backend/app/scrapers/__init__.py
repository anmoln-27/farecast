"""
backend/app/scrapers/__init__.py
--------------------------------
Multi-Source Web Scraping & Ingestion Engine for Indian Domestic Aviation.
"""
from backend.app.scrapers.base import BaseScraper
from backend.app.scrapers.airline_scrapers import (
    IndiGoScraper,
    AirIndiaScraper,
    AirIndiaExpressScraper,
    AkasaAirScraper,
    SpiceJetScraper,
    OTAScraper,
)
from backend.app.scrapers.orchestrator import ScraperOrchestrator

__all__ = [
    "BaseScraper",
    "IndiGoScraper",
    "AirIndiaScraper",
    "AirIndiaExpressScraper",
    "AkasaAirScraper",
    "SpiceJetScraper",
    "OTAScraper",
    "ScraperOrchestrator",
]
