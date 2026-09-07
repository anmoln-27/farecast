"""
backend/app/api/routers/scrapers.py
-----------------------------------
API endpoints for:
- GET /api/scrapers/compliance: Real-time ethical scraping compliance and accessibility audit
- POST /api/scrapers/sweep: Trigger polite multi-source data sweep

Adheres to SIH ethical scraping standards:
- Verifies robots.txt permissions
- Identifies bot-management systems (Akamai, Cloudflare, PerimeterX)
- Never bypasses CAPTCHAs
- Never fabricates simulated data as LIVE
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query
from pydantic import BaseModel

from backend.app.scrapers.airline_scrapers import (
    AirIndiaExpressScraper,
    AirIndiaScraper,
    AkasaAirScraper,
    EaseMyTripScraper,
    IndiGoScraper,
    OTAScraper,
    SpiceJetScraper,
)
from backend.app.scrapers.orchestrator import ScraperOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scrapers", tags=["Scrapers & Compliance"])


class ComplianceAuditItem(BaseModel):
    airline_code: str
    airline_name: str
    base_url: str
    robots_url: str
    robots_allowed: bool
    http_status: Optional[int] = None
    access_state: str
    anti_bot_detected: Optional[str] = None
    details: str
    legal_compliance_rule: str


class ComplianceReportResponse(BaseModel):
    disclaimer: str = (
        "SIH 26056 Ethical Scraping Compliance Report. "
        "Adheres to legal constraints, robots.txt directives, and does NOT circumvent anti-bot WAFs. "
        "Any restricted sources are reported transparently."
    )
    total_sources: int
    accessible_count: int
    restricted_count: int
    sources: list[ComplianceAuditItem]


@router.get("/compliance", response_model=ComplianceReportResponse, summary="Source compliance audit")
def get_compliance_report() -> ComplianceReportResponse:
    """
    Audit all registered Indian airline and OTA source adapters for robots.txt compliance
    and WAF / anti-bot restrictions.
    """
    import concurrent.futures

    scrapers = [
        IndiGoScraper(),
        AirIndiaScraper(),
        AirIndiaExpressScraper(),
        AkasaAirScraper(),
        SpiceJetScraper(),
        OTAScraper(),
        EaseMyTripScraper(),
    ]

    def _audit_one(sc) -> ComplianceAuditItem:
        try:
            status = sc.check_compliance_status("/")
            return ComplianceAuditItem(**status)
        except Exception as exc:
            logger.error("Compliance check failed for %s: %s", sc.airline_name, exc)
            return ComplianceAuditItem(
                airline_code=sc.airline_code,
                airline_name=sc.airline_name,
                base_url=sc.base_url,
                robots_url=f"{sc.base_url}/robots.txt",
                robots_allowed=False,
                access_state="AUDIT_ERROR",
                details=str(exc),
                legal_compliance_rule="Audit failed gracefully; zero fabricated data.",
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
        items = list(executor.map(_audit_one, scrapers))

    accessible = sum(1 for item in items if item.robots_allowed and "ACCESSIBLE" in item.access_state)
    restricted = len(items) - accessible

    return ComplianceReportResponse(
        total_sources=len(items),
        accessible_count=accessible,
        restricted_count=restricted,
        sources=items,
    )


@router.post("/sweep", summary="Trigger multi-source scraper sweep")
def trigger_sweep(
    simulate: bool = Query(default=True, description="True for methodology demonstration (DEMO data mode)"),
    save_to_db: bool = Query(default=False, description="Persist cleaned sweep results to database"),
) -> dict:
    """
    Execute a multi-source scraper sweep.
    When simulate=True, all records are strictly tagged data_mode='DEMO'.
    """
    orchestrator = ScraperOrchestrator()
    result = orchestrator.run_sweep(simulate=simulate, save_to_db=save_to_db)
    result["mode_note"] = "Simulation run tagged DEMO" if simulate else "Compliant live sweep"
    return result
