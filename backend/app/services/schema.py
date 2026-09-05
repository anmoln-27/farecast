"""
backend/app/services/schema.py
-------------------------------
Common fare observation schema (dataclass + Pydantic model).

All fare data — regardless of source (Kaggle, GitHub, Amadeus, Demo) —
is normalised into FareRecord before being persisted.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Canonical airport/city lookup
# ─────────────────────────────────────────────────────────────────────────────

CITY_TO_IATA: dict[str, str] = {
    "delhi": "DEL",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "bombay": "BOM",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "hyderabad": "HYD",
    "kolkata": "CCU",
    "calcutta": "CCU",
    "chennai": "MAA",
    "madras": "MAA",
    "ahmedabad": "AMD",
    "goa": "GOI",
    "pune": "PNQ",
    "cochin": "COK",
    "kochi": "COK",
    "jaipur": "JAI",
    "lucknow": "LKO",
    "bhubaneswar": "BBI",
    "guwahati": "GAU",
    "srinagar": "SXR",
    "amritsar": "ATQ",
    "nagpur": "NAG",
    "indore": "IDR",
    "patna": "PAT",
    "ranchi": "IXR",
    "raipur": "RPR",
    "chandigarh": "IXC",
    "visakhapatnam": "VTZ",
    "vizag": "VTZ",
    "coimbatore": "CJB",
    "trivandrum": "TRV",
    "thiruvananthapuram": "TRV",
    "vadodara": "BDQ",
    "surat": "STV",
    "bagdogra": "IXB",
    "leh": "IXL",
}

AIRLINE_NAME_NORMALISE: dict[str, str] = {
    "indigo": "IndiGo",
    "air india": "Air India",
    "air_india": "Air India",
    "spicejet": "SpiceJet",
    "spice jet": "SpiceJet",
    "vistara": "Vistara",
    "go first": "Go First",
    "go_first": "Go First",
    "goair": "Go First",
    "go air": "Go First",
    "air asia": "Air Asia India",
    "airasiaind": "Air Asia India",
    "air asia india": "Air Asia India",
    "akasa": "Akasa Air",
    "akasa air": "Akasa Air",
    "air india express": "Air India Express",
    "ix": "Air India Express",
    "jet airways": "Jet Airways",
}

DEPARTURE_TIME_PERIODS: dict[str, str] = {
    "early morning": "Early Morning",
    "morning": "Morning",
    "afternoon": "Afternoon",
    "evening": "Evening",
    "night": "Night",
    "late night": "Late Night",
}


def normalise_city(city: str) -> str:
    """Return IATA code for known Indian cities, else return uppercased input."""
    if not city:
        return ""
    cleaned = city.strip().lower()
    return CITY_TO_IATA.get(cleaned, city.strip().upper())


def normalise_airline(airline: str) -> str:
    """Return canonical airline name."""
    if not airline:
        return ""
    cleaned = airline.strip().lower()
    return AIRLINE_NAME_NORMALISE.get(cleaned, airline.strip().title())


def normalise_time_period(value: str) -> str:
    """Normalise departure/arrival time label."""
    if not value:
        return ""
    cleaned = value.strip().lower()
    return DEPARTURE_TIME_PERIODS.get(cleaned, value.strip().title())


# ─────────────────────────────────────────────────────────────────────────────
# Common FareRecord dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FareRecord:
    """
    Normalised fare observation — the canonical in-memory representation
    before database persistence.

    Fields match the fare_observations table in db/models.py.
    """

    # Provenance
    source: str                          # "kaggle" | "github_full_fare" | "amadeus" | "demo"
    data_mode: str = "HISTORICAL"        # "LIVE" | "HISTORICAL" | "DEMO"

    # Airline / Flight
    airline_code: Optional[str] = None
    flight_number: Optional[str] = None

    # Route
    origin: str = ""
    destination: str = ""

    # Travel timing
    travel_date: Optional[date] = None
    booking_date: Optional[date] = None
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None

    # Trip details
    stops: int = 0
    duration_minutes: Optional[int] = None
    cabin_class: str = "Economy"

    # Fare — always numeric INR
    fare: float = 0.0
    currency: str = "INR"

    # Derived
    days_left: Optional[int] = None

    # Timestamps
    collected_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def fingerprint(self) -> str:
        """
        Deterministic hash for deduplication.
        Two records with the same route/airline/date/fare/class are duplicates.
        """
        key = json.dumps(
            {
                "source": self.source,
                "airline_code": self.airline_code,
                "origin": self.origin,
                "destination": self.destination,
                "travel_date": str(self.travel_date),
                "departure_time": self.departure_time,
                "stops": self.stops,
                "cabin_class": self.cabin_class,
                "fare": round(self.fare, 2),
            },
            sort_keys=True,
        )
        return hashlib.md5(key.encode()).hexdigest()
