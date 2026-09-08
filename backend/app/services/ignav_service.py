"""
backend/app/services/ignav_service.py
--------------------------------------
Ignav Live Airfare API integration.

SECURITY RULES (strictly enforced):
  - Credentials (IGNAV_API_KEY) are read EXCLUSIVELY from settings (server environment).
  - The API key is NEVER logged, printed, or returned to callers.
  - Headers and error traces redact sensitive authorization material.

API PROTOCOL:
  - Base URL: Configurable via settings.IGNAV_BASE_URL (default: https://ignav.com).
  - Endpoint: POST /api/fares/one-way
  - Header: X-Api-Key: <IGNAV_API_KEY>
  - Body: JSON { origin, destination, departure_date, adults, cabin_class, market }
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from backend.app.core.config import Settings

logger = logging.getLogger(__name__)


class IgnavConfigError(RuntimeError):
    """Raised when Ignav API key is not configured."""


class IgnavAuthError(RuntimeError):
    """Raised when Ignav authentication or authorization fails."""


class IgnavSearchError(RuntimeError):
    """Raised when Ignav flight search fails."""


class IgnavService:
    """
    Adapter for the Ignav Public API (v1.0.0).
    Provides one-way live flight searches normalized into FareCast structure.
    """

    def __init__(
        self,
        settings: Settings,
        http_session: Optional[requests.Session] = None,
    ):
        self._settings = settings
        self._base_url = (settings.IGNAV_BASE_URL or "https://ignav.com").rstrip("/")
        self._api_key = settings.IGNAV_API_KEY
        self._http = http_session or requests.Session()

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        adults: int = 1,
        travel_class: str = "ECONOMY",
        max_results: int = 10,
        market: str = "IN",
    ) -> List[Dict[str, Any]]:
        """
        Search Ignav for one-way flight offers.

        Args:
            origin: IATA origin code, e.g. "DEL"
            destination: IATA destination code, e.g. "BOM"
            departure_date: ISO date YYYY-MM-DD
            adults: Number of passengers (1-9)
            travel_class: ECONOMY / PREMIUM_ECONOMY / BUSINESS / FIRST
            max_results: Max offers to return
            market: Country market code, default "IN"

        Returns:
            List of normalized fare offer dictionaries.
        """
        if not self._api_key:
            raise IgnavConfigError("IGNAV_API_KEY is not configured on the server.")

        endpoint = f"{self._base_url}/api/fares/one-way"
        cabin_mapped = self._normalize_cabin_request(travel_class)

        payload: Dict[str, Any] = {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "departure_date": departure_date,
            "adults": max(1, adults),
            "cabin_class": cabin_mapped,
            "market": market.upper() if market else "IN",
        }

        headers = {
            "X-Api-Key": self._api_key,
            "Content-Type": "application/json",
            "User-Agent": "FareCast/4.0",
        }

        # Safe request execution with at most one controlled retry on network drop/503/504
        resp = None
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                resp = self._http.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=15,
                )
                if resp.status_code in (503, 504) and attempt < max_attempts:
                    logger.warning(
                        "Ignav transient error %d on attempt %d; performing controlled single retry",
                        resp.status_code,
                        attempt,
                    )
                    continue
                break
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt < max_attempts:
                    logger.warning(
                        "Ignav network timeout on attempt %d; performing controlled single retry",
                        attempt,
                    )
                    continue
                logger.error("Ignav request connection failure: %s", type(exc).__name__)
                raise IgnavSearchError(f"Ignav connection failed: {type(exc).__name__}") from exc
            except requests.RequestException as exc:
                logger.error("Ignav request failure: %s", type(exc).__name__)
                raise IgnavSearchError(f"Ignav request failed: {type(exc).__name__}") from exc

        if resp is None:
            raise IgnavSearchError("Ignav request produced no response.")

        if resp.status_code in (401, 403):
            logger.error("Ignav authorization failed (HTTP %d)", resp.status_code)
            raise IgnavAuthError("Ignav API authentication/authorization failed. Check server configuration.")

        if resp.status_code >= 400:
            logger.error("Ignav search returned HTTP %d", resp.status_code)
            raise IgnavSearchError(f"Ignav API returned error status {resp.status_code}.")

        try:
            data = resp.json()
        except Exception as exc:
            logger.error("Ignav returned non-JSON payload: %s", type(exc).__name__)
            raise IgnavSearchError("Failed to parse Ignav response JSON.") from exc

        itineraries = data.get("itineraries", [])
        if not isinstance(itineraries, list):
            itineraries = []

        normalized: List[Dict[str, Any]] = []
        for itin in itineraries[:max_results]:
            offer = self._normalize_itinerary(
                itin=itin,
                origin=origin.upper(),
                destination=destination.upper(),
                requested_date=departure_date,
            )
            if offer:
                normalized.append(offer)

        return normalized

    def _normalize_itinerary(
        self,
        itin: Dict[str, Any],
        origin: str,
        destination: str,
        requested_date: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Convert an Ignav ItineraryModel into FareCast's common fare structure.
        """
        price_block = itin.get("price", {})
        try:
            fare = float(price_block.get("amount", 0.0))
        except (ValueError, TypeError):
            fare = 0.0

        currency = price_block.get("currency", "INR") or "INR"

        outbound = itin.get("outbound") or {}
        segments = outbound.get("segments") or []

        carrier = outbound.get("carrier")
        duration_minutes = outbound.get("duration_minutes")

        airline_code = carrier
        airline_name: Optional[str] = None
        flight_number_str: Optional[str] = None
        dep_datetime: Optional[str] = None
        arr_datetime: Optional[str] = None

        if segments:
            first_seg = segments[0]
            last_seg = segments[-1]

            marketing_code = first_seg.get("marketing_carrier_code")
            if not airline_code and marketing_code:
                airline_code = marketing_code

            airline_name = first_seg.get("operating_carrier_name") or first_seg.get("marketing_carrier_code")

            raw_fn = first_seg.get("flight_number")
            if raw_fn:
                flight_number_str = f"{airline_code}-{raw_fn}" if airline_code and not str(raw_fn).startswith(airline_code) else str(raw_fn)

            dep_datetime = first_seg.get("departure_time_local") or first_seg.get("departure_time_utc")
            arr_datetime = last_seg.get("arrival_time_local") or last_seg.get("arrival_time_utc")

            if duration_minutes is None:
                duration_minutes = sum(s.get("duration_minutes", 0) for s in segments if isinstance(s.get("duration_minutes"), int))

        stops = max(0, len(segments) - 1)
        cabin_class = self._normalize_cabin_display(itin.get("cabin_class"))

        fare_inr_estimate = fare if currency.upper() == "INR" else None

        return {
            "source": "IGNAV",
            "data_mode": "LIVE",
            "origin": origin,
            "destination": destination,
            "airline_code": (airline_code or "6E").upper(),
            "airline_name": airline_name,
            "flight_number": flight_number_str,
            "departure_datetime": dep_datetime,
            "arrival_datetime": arr_datetime,
            "duration_minutes": duration_minutes,
            "stops": stops,
            "cabin_class": cabin_class,
            "fare": fare,
            "currency": currency.upper(),
            "fare_inr_estimate": fare_inr_estimate,
            "collected_at": datetime.now(timezone.utc),
            "segments": segments,
        }

    @staticmethod
    def _normalize_cabin_request(travel_class: str) -> str:
        mapping = {
            "economy": "economy",
            "premium_economy": "premium_economy",
            "premium economy": "premium_economy",
            "business": "business",
            "first": "first",
        }
        return mapping.get(travel_class.strip().lower(), "economy")

    @staticmethod
    def _normalize_cabin_display(raw_cabin: Optional[str]) -> str:
        if not raw_cabin:
            return "Economy"
        mapping = {
            "economy": "Economy",
            "premium_economy": "Premium Economy",
            "premium economy": "Premium Economy",
            "business": "Business",
            "first": "First",
        }
        return mapping.get(raw_cabin.strip().lower(), "Economy")


def get_ignav_service(settings: Settings) -> IgnavService:
    """Factory creating configured IgnavService instance."""
    return IgnavService(settings)
