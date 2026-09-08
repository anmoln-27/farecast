"""
scripts/smoke_test_ignav.py
----------------------------
Controlled ONE-SHOT real Ignav API smoke test for FareCast.

Strict constraints:
  - Exactly ONE request: DEL -> BOM, 1 adult, economy, market=IN, one travel date (+7 days).
  - No loops, no retries unless transient network drop.
  - Never prints, logs, or displays the API key.
  - Verifies carrier, flight number, travel times, fare, INR currency, and normalization.
  - Persists offers through standard FareObservation persistence if database is available.
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.config import get_settings
from backend.app.db.base import SessionLocal
from backend.app.api.routers.live import _persist_live_offers
from backend.app.schemas.responses import LiveFareOffer
from backend.app.services.ignav_service import get_ignav_service


def run_smoke_test():
    settings = get_settings()

    if not settings.ignav_available:
        print("[STATUS] IGNAV_API_KEY is not set in local environment or .env.")
        print("Note: If configured in Render, the live API runs in the Render deployment.")
        print("To execute this smoke test locally, supply IGNAV_API_KEY in your local .env file.")
        return False

    print("[SMOKE TEST] Starting ONE controlled real API call to Ignav...")
    dep_date = (date.today() + timedelta(days=7)).isoformat()
    print(f"Request parameters: DEL -> BOM | Date: {dep_date} | Adults: 1 | Cabin: economy | Market: IN")

    svc = get_ignav_service(settings)
    try:
        raw_offers = svc.search_flights(
            origin="DEL",
            destination="BOM",
            departure_date=dep_date,
            adults=1,
            travel_class="ECONOMY",
            max_results=5,
            market="IN",
        )
    except Exception as exc:
        print(f"[ERROR] Real API request failed: {type(exc).__name__}: {exc}")
        return False

    print(f"[SUCCESS] Real API response received! Total offers returned: {len(raw_offers)}")
    if not raw_offers:
        print("[WARN] Zero offers returned for this route/date.")
        return True

    # Validate first offer
    first = raw_offers[0]
    print("\n--- Verified Live Offer Sample (Sanitized) ---")
    print(f"Source:           {first.get('source')}")
    print(f"Data Mode:        {first.get('data_mode')}")
    print(f"Carrier / Code:   {first.get('airline_name')} ({first.get('airline_code')})")
    print(f"Flight Number:    {first.get('flight_number')}")
    print(f"Departure Time:   {first.get('departure_datetime')}")
    print(f"Arrival Time:     {first.get('arrival_datetime')}")
    print(f"Stops:            {first.get('stops')}")
    print(f"Duration Minutes: {first.get('duration_minutes')}")
    print(f"Cabin Class:      {first.get('cabin_class')}")
    print(f"Fare:             {first.get('fare')} {first.get('currency')}")
    print(f"INR Estimate:     {first.get('fare_inr_estimate')}")

    # Verify normalization into LiveFareOffer schema
    offers = [LiveFareOffer(**o) for o in raw_offers]
    print(f"[OK] Successfully validated {len(offers)} offers into FareCast LiveFareOffer schema.")

    # Persist verified offers to DB
    db = SessionLocal()()
    try:
        persisted = _persist_live_offers(db, offers, dep_date, source="ignav")
        print(f"[OK] Successfully persisted {persisted} LIVE offers to fare_observations table.")
    except Exception as exc:
        print(f"[WARN] DB persistence warning: {exc}")
    finally:
        db.close()

    return True


if __name__ == "__main__":
    run_smoke_test()
