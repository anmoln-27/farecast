"""
backend/app/services/amadeus_service.py
-----------------------------------------
Amadeus Flight Offers Search integration.

SECURITY RULES (enforced here):
  - Credentials are read EXCLUSIVELY from settings (environment variables).
  - The client secret is NEVER logged, printed, or returned to callers.
  - This module is only called when DEMO_MODE=false AND credentials are configured.

COVERAGE NOTE:
  Amadeus test API coverage does NOT include every Indian domestic airline.
  Results must be labelled source="AMADEUS", data_mode="LIVE".
  Do NOT claim this represents complete Indian airfare coverage.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from backend.app.core.config import Settings

logger = logging.getLogger(__name__)

# EUR→INR approximate conversion factor (informational only; not a financial rate)
_EUR_INR_APPROX = 90.0


class AmadeusAuthError(RuntimeError):
    """Raised when OAuth2 token fetch fails."""


class AmadeusSearchError(RuntimeError):
    """Raised when Flight Offers Search fails."""


class AmadeusService:
    """
    Thin wrapper around Amadeus Flight Offers Search v2.

    Credentials are passed via Settings and NEVER stored as plain strings
    beyond the lifetime of the token-fetch request.
    """

    def __init__(self, settings: Settings, http_session: Optional[requests.Session] = None):
        self._settings = settings
        self._base_url = settings.AMADEUS_BASE_URL.rstrip("/")
        self._token: Optional[str] = None
        self._http = http_session or requests.Session()
        self._http.headers.update({"User-Agent": "FareCast/4.0"})

    # ─── OAuth2 ────────────────────────────────────────────────────────────────

    def _fetch_token(self) -> str:
        """
        Obtain a short-lived OAuth2 access token using client credentials.
        The client secret is sent ONLY in this request body and never stored
        or returned.
        """
        token_url = f"{self._base_url}/v1/security/oauth2/token"
        try:
            resp = self._http.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._settings.AMADEUS_CLIENT_ID,
                    "client_secret": self._settings.AMADEUS_CLIENT_SECRET,
                },
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            # Do NOT include any credential data in the log message
            logger.error("Amadeus token fetch failed: %s", type(exc).__name__)
            raise AmadeusAuthError("Failed to obtain Amadeus access token.") from exc

        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise AmadeusAuthError("Amadeus token response missing access_token field.")
        return token

    def _ensure_token(self) -> str:
        """Return a valid access token, fetching a new one if needed."""
        if not self._token:
            self._token = self._fetch_token()
        return self._token

    # ─── Flight Offers Search ──────────────────────────────────────────────────

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        adults: int = 1,
        travel_class: str = "ECONOMY",
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search Amadeus Flight Offers for a one-way trip.

        Args:
            origin:         IATA airport code (e.g. "DEL")
            destination:    IATA airport code (e.g. "BOM")
            departure_date: ISO date string (e.g. "2024-03-15")
            adults:         number of adult passengers
            travel_class:   ECONOMY | PREMIUM_ECONOMY | BUSINESS | FIRST
            max_results:    max offers to return

        Returns:
            List of normalised fare offer dicts.

        Coverage note: Amadeus test API may not cover all Indian domestic airlines.
        """
        token = self._ensure_token()
        search_url = f"{self._base_url}/v2/shopping/flight-offers"

        params = {
            "originLocationCode": origin.upper(),
            "destinationLocationCode": destination.upper(),
            "departureDate": departure_date,
            "adults": adults,
            "travelClass": travel_class.upper(),
            "max": max_results,
            "currencyCode": "EUR",
        }

        try:
            resp = self._http.get(
                search_url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            # If token expired mid-session, refresh once
            if resp.status_code == 401:
                self._token = None
                token = self._ensure_token()
                resp = self._http.get(
                    search_url,
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=15,
                )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Amadeus flight search failed: %s", type(exc).__name__)
            raise AmadeusSearchError(f"Amadeus search request failed: {type(exc).__name__}") from exc

        raw = resp.json()
        offers = raw.get("data", [])
        return [self._normalize_offer(offer, origin, destination) for offer in offers]

    # ─── Normalisation ─────────────────────────────────────────────────────────

    def _normalize_offer(
        self, offer: dict[str, Any], origin: str, destination: str
    ) -> dict[str, Any]:
        """
        Normalise a raw Amadeus Flight Offer into the project's common fare structure.
        source="AMADEUS", data_mode="LIVE", collected_at=now().
        """
        collected_at = datetime.now(timezone.utc)

        # Price
        price_block = offer.get("price", {})
        fare_eur = float(price_block.get("grandTotal", price_block.get("total", 0)))
        fare_inr_estimate = round(fare_eur * _EUR_INR_APPROX, 2)

        # Itinerary
        itineraries = offer.get("itineraries", [])
        segments: list[dict] = []
        stops = 0
        duration_minutes: Optional[int] = None
        airline_code: Optional[str] = None
        departure_dt: Optional[str] = None
        arrival_dt: Optional[str] = None
        cabin_class = "Economy"

        if itineraries:
            first_itin = itineraries[0]
            # Parse ISO 8601 duration (e.g. PT2H30M)
            raw_dur = first_itin.get("duration", "")
            duration_minutes = _parse_iso_duration(raw_dur)

            segs = first_itin.get("segments", [])
            stops = max(0, len(segs) - 1)

            if segs:
                first_seg = segs[0]
                last_seg = segs[-1]
                departure_dt = first_seg.get("departure", {}).get("at")
                arrival_dt = last_seg.get("arrival", {}).get("at")
                airline_code = first_seg.get("carrierCode")

            segments = segs

        # Cabin class from travelerPricings
        traveler_pricings = offer.get("travelerPricings", [])
        if traveler_pricings:
            fare_details = traveler_pricings[0].get("fareDetailsBySegment", [])
            if fare_details:
                raw_cabin = fare_details[0].get("cabin", "ECONOMY")
                cabin_class = _normalize_cabin(raw_cabin)

        return {
            "source": "AMADEUS",
            "data_mode": "LIVE",
            "origin": origin.upper(),
            "destination": destination.upper(),
            "airline_code": airline_code,
            "airline_name": None,  # Lookup not done to avoid extra API call
            "departure_datetime": departure_dt,
            "arrival_datetime": arrival_dt,
            "duration_minutes": duration_minutes,
            "stops": stops,
            "cabin_class": cabin_class,
            "fare": fare_eur,
            "currency": "EUR",
            "fare_inr_estimate": fare_inr_estimate,
            "collected_at": collected_at,
            "segments": segments,
        }

    # ─── Connectivity check ───────────────────────────────────────────────────

    def check_connectivity(self) -> bool:
        """
        Attempt to fetch a token to verify Amadeus is reachable.
        Returns True if successful, False otherwise.
        Never raises — safe to call for status checks.
        """
        try:
            self._token = None
            self._fetch_token()
            return True
        except Exception:
            return False


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_iso_duration(duration_str: str) -> Optional[int]:
    """Parse ISO 8601 duration PT2H30M -> minutes."""
    if not duration_str or not duration_str.startswith("PT"):
        return None
    s = duration_str[2:]  # strip PT
    hours = 0
    minutes = 0
    if "H" in s:
        h_part, s = s.split("H", 1)
        try:
            hours = int(h_part)
        except ValueError:
            pass
    if "M" in s:
        m_part = s.split("M")[0]
        try:
            minutes = int(m_part)
        except ValueError:
            pass
    return hours * 60 + minutes


def _normalize_cabin(raw: str) -> str:
    mapping = {
        "ECONOMY": "Economy",
        "PREMIUM_ECONOMY": "Premium Economy",
        "BUSINESS": "Business",
        "FIRST": "First",
    }
    return mapping.get(raw.upper(), "Economy")


# ─── Factory ──────────────────────────────────────────────────────────────────

def get_amadeus_service(settings: Settings) -> AmadeusService:
    """Create a configured AmadeusService from Settings."""
    return AmadeusService(settings)
