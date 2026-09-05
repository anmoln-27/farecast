"""
tests/test_cleaning.py
-----------------------
Pytest tests for the data cleaning pipeline.
"""
import pytest
from datetime import date

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.services.schema import (
    FareRecord,
    normalise_city,
    normalise_airline,
)
from backend.app.services.cleaner import (
    clean_fare_records,
    _parse_duration,
    _normalise_cabin,
    FARE_MIN_INR,
    FARE_MAX_INR,
)


# ── Normalisation tests ───────────────────────────────────────────────────────

class TestCityNormalisation:
    def test_known_city_delhi(self):
        assert normalise_city("delhi") == "DEL"

    def test_known_city_mumbai(self):
        assert normalise_city("Mumbai") == "BOM"

    def test_known_city_bangalore(self):
        assert normalise_city("Bangalore") == "BLR"
        assert normalise_city("Bengaluru") == "BLR"

    def test_unknown_city_passthrough(self):
        # Unknown cities are returned as uppercased
        result = normalise_city("Shimla")
        assert result == "SHIMLA"

    def test_empty_city(self):
        assert normalise_city("") == ""

    def test_iata_passthrough(self):
        # If IATA code is passed directly, it passes through uppercased
        assert normalise_city("DEL") == "DEL"


class TestAirlineNormalisation:
    def test_indigo(self):
        assert normalise_airline("indigo") == "IndiGo"

    def test_air_india(self):
        assert normalise_airline("air india") == "Air India"

    def test_spicejet(self):
        assert normalise_airline("SpiceJet") == "SpiceJet"

    def test_unknown_airline(self):
        result = normalise_airline("FlyDubai")
        assert result == "Flydubai"  # title-cased

    def test_empty_airline(self):
        assert normalise_airline("") == ""


# ── Duration parsing tests ────────────────────────────────────────────────────

class TestDurationParsing:
    def test_hours_minutes_format(self):
        assert _parse_duration("2h 30m") == 150

    def test_hours_only(self):
        assert _parse_duration("3h") == 180

    def test_numeric_float(self):
        assert _parse_duration(90.0) == 90

    def test_numeric_int(self):
        assert _parse_duration(120) == 120

    def test_colon_format(self):
        assert _parse_duration("1:45") == 105

    def test_invalid_returns_none(self):
        assert _parse_duration("invalid") is None

    def test_none_returns_none(self):
        assert _parse_duration(None) is None

    def test_zero_returns_none(self):
        assert _parse_duration(0) is None


# ── Cabin class normalisation ─────────────────────────────────────────────────

class TestCabinNormalisation:
    def test_economy(self):
        assert _normalise_cabin("economy") == "Economy"

    def test_business(self):
        assert _normalise_cabin("Business Class") == "Business"

    def test_premium_economy(self):
        assert _normalise_cabin("Premium Economy") == "Premium Economy"

    def test_first(self):
        assert _normalise_cabin("First") == "First"

    def test_none_defaults_economy(self):
        assert _normalise_cabin(None) == "Economy"

    def test_unknown_defaults_economy(self):
        assert _normalise_cabin("Unknown") == "Economy"


# ── Cleaning pipeline tests ───────────────────────────────────────────────────

def _make_record(**kwargs) -> FareRecord:
    defaults = {
        "source": "test",
        "data_mode": "HISTORICAL",
        "airline_code": "IndiGo",
        "origin": "Delhi",
        "destination": "Mumbai",
        "fare": 5000.0,
        "cabin_class": "Economy",
        "stops": 0,
        "duration_minutes": 120,
        "days_left": 30,
    }
    defaults.update(kwargs)
    return FareRecord(**defaults)


class TestCleanFareRecords:
    def test_valid_record_passes(self):
        records = [_make_record()]
        cleaned, report = clean_fare_records(records, source="test")
        assert len(cleaned) == 1
        assert report.output_count == 1

    def test_missing_fare_dropped(self):
        records = [_make_record(fare=None)]
        cleaned, report = clean_fare_records(records, source="test")
        assert len(cleaned) == 0
        assert report.dropped_missing_required == 1

    def test_missing_origin_dropped(self):
        records = [_make_record(origin="")]
        cleaned, report = clean_fare_records(records, source="test")
        assert len(cleaned) == 0

    def test_fare_too_low_dropped(self):
        records = [_make_record(fare=100.0)]
        cleaned, report = clean_fare_records(records, source="test")
        assert len(cleaned) == 0
        assert report.dropped_impossible_fare == 1

    def test_fare_too_high_dropped(self):
        records = [_make_record(fare=5_000_000.0)]
        cleaned, report = clean_fare_records(records, source="test")
        assert len(cleaned) == 0
        assert report.dropped_impossible_fare == 1

    def test_same_origin_destination_dropped(self):
        records = [_make_record(origin="Mumbai", destination="Mumbai")]
        cleaned, report = clean_fare_records(records, source="test")
        assert len(cleaned) == 0
        assert report.dropped_invalid_route == 1

    def test_duplicate_fingerprint_removed(self):
        r1 = _make_record()
        r2 = _make_record()  # Identical → duplicate
        cleaned, report = clean_fare_records([r1, r2], source="test")
        assert len(cleaned) == 1
        assert report.dropped_duplicates == 1

    def test_cities_normalised(self):
        records = [_make_record(origin="delhi", destination="mumbai")]
        cleaned, _ = clean_fare_records(records, source="test")
        assert cleaned[0].origin == "DEL"
        assert cleaned[0].destination == "BOM"

    def test_negative_days_left_cleared(self):
        records = [_make_record(days_left=-5)]
        cleaned, _ = clean_fare_records(records, source="test")
        assert cleaned[0].days_left is None

    def test_days_left_over_365_cleared(self):
        records = [_make_record(days_left=400)]
        cleaned, _ = clean_fare_records(records, source="test")
        assert cleaned[0].days_left is None

    def test_cabin_normalised(self):
        records = [_make_record(cabin_class="business class")]
        cleaned, _ = clean_fare_records(records, source="test")
        assert cleaned[0].cabin_class == "Business"


# ── Schema tests ──────────────────────────────────────────────────────────────

class TestFareSchema:
    def test_fingerprint_deterministic(self):
        r1 = _make_record()
        r2 = _make_record()
        assert r1.fingerprint() == r2.fingerprint()

    def test_fingerprint_differs_on_fare(self):
        r1 = _make_record(fare=5000.0)
        r2 = _make_record(fare=6000.0)
        assert r1.fingerprint() != r2.fingerprint()

    def test_fingerprint_differs_on_route(self):
        r1 = _make_record(origin="Delhi", destination="Mumbai")
        r2 = _make_record(origin="Delhi", destination="Chennai")
        assert r1.fingerprint() != r2.fingerprint()

    def test_to_dict(self):
        r = _make_record()
        d = r.to_dict()
        assert isinstance(d, dict)
        assert "fare" in d
        assert "source" in d
