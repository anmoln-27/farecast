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
# Airport User Development Fee (UDF) Rates & Disaggregation
# ─────────────────────────────────────────────────────────────────────────────

AIRPORT_UDF_RATES: dict[str, float] = {
    "DEL": 300.0,
    "BOM": 275.0,
    "BLR": 350.0,
    "HYD": 380.0,
    "CCU": 250.0,
    "MAA": 220.0,
    "AMD": 210.0,
    "PNQ": 180.0,
    "GOI": 200.0,
    "COK": 220.0,
    "JAI": 190.0,
    "LKO": 200.0,
    "GAU": 150.0,
    "PAT": 150.0,
    "SXR": 150.0,
    "DEFAULT": 200.0,
}


def compute_fare_disaggregation(
    total_fare: float,
    origin: str = "",
    airline_code: Optional[str] = None,
) -> dict[str, float]:
    """
    Reference Tariff Decomposition — Estimated.
    Estimates a breakdown of total gross fare into:
    Base Fare, Taxes & Surcharges, UDF (User Development Fee), and Convenience Fee.
    NOT observed source data — this is a reference heuristic model.
    Guarantees: base_fare + taxes + udf_charge + convenience_fee == round(total_fare, 2).
    """
    total = round(float(total_fare), 2)
    if total <= 0:
        return {
            "base_fare": 0.0,
            "taxes": 0.0,
            "udf_charge": 0.0,
            "convenience_fee": 0.0,
            "total_fare": 0.0,
        }

    conv_fee = 350.0 if total >= 1500.0 else 0.0
    norm_origin = normalise_city(origin) if origin else ""
    udf = AIRPORT_UDF_RATES.get(norm_origin, AIRPORT_UDF_RATES["DEFAULT"])
    if total < conv_fee + udf + 500.0:
        udf = round(total * 0.05, 2)
        conv_fee = round(total * 0.05, 2)

    rem = max(0.0, total - conv_fee - udf)
    base_fare = round(rem * 0.72, 2)
    taxes = round(total - base_fare - udf - conv_fee, 2)

    return {
        "base_fare": base_fare,
        "taxes": taxes,
        "udf_charge": udf,
        "convenience_fee": conv_fee,
        "total_fare": total,
    }


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
    source: str                          # "kaggle" | "github_full_fare" | "amadeus" | "demo" | "scraper"
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

    # Fare Disaggregation
    base_fare: Optional[float] = None
    taxes: Optional[float] = None
    udf_charge: Optional[float] = None
    convenience_fee: Optional[float] = None
    total_fare: Optional[float] = None

    # Advance purchase window & availability status
    advance_window: Optional[str] = None  # 'T+1', 'T+7', 'T+15', 'T+30', 'T+45'
    status: str = "AVAILABLE"             # 'AVAILABLE', 'SOLD_OUT', 'CANCELLED'

    # Derived
    days_left: Optional[int] = None

    # Timestamps
    collected_at: Optional[datetime] = None

    def __post_init__(self):
        if self.total_fare is None and self.fare:
            self.total_fare = round(float(self.fare), 2)
        elif (self.fare == 0.0 or self.fare is None) and self.total_fare:
            self.fare = round(float(self.total_fare), 2)

        if self.advance_window is None and self.days_left is not None:
            if self.days_left <= 1:
                self.advance_window = "T+1"
            elif self.days_left <= 7:
                self.advance_window = "T+7"
            elif self.days_left <= 15:
                self.advance_window = "T+15"
            elif self.days_left <= 30:
                self.advance_window = "T+30"
            else:
                self.advance_window = "T+45"

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
                "flight_number": self.flight_number,
                "origin": self.origin,
                "destination": self.destination,
                "travel_date": str(self.travel_date),
                "departure_time": self.departure_time,
                "arrival_time": self.arrival_time,
                "stops": self.stops,
                "duration_minutes": self.duration_minutes,
                "cabin_class": self.cabin_class,
                "days_left": self.days_left,
                "fare": round(self.fare, 2),
            },
            sort_keys=True,
        )
        return hashlib.md5(key.encode()).hexdigest()
