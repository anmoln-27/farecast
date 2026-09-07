"""
backend/app/services/cleaner.py
--------------------------------
Data cleaning pipeline for fare observations.

Rules applied (in order):
1. Drop rows missing required fields (origin, destination, fare).
2. Remove impossible fares (negative, zero for commercial routes, > 2,000,000 INR).
3. Standardise city/airport codes → IATA via schema.normalise_city.
4. Standardise airline names → canonical form.
5. Convert duration to minutes.
6. Clip extreme days_left values (< 0 or > 365).
7. Normalise cabin_class to allowed enum values.
8. Remove duplicate fingerprints within a batch.

Returns a cleaned list[FareRecord] and a CleaningReport.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from backend.app.services.schema import (
    FareRecord,
    normalise_airline,
    normalise_city,
    normalise_time_period,
)

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
FARE_MIN_INR = 500          # below this is almost certainly an error
FARE_MAX_INR = 2_000_000    # above this is almost certainly an error
DAYS_LEFT_MAX = 365
ALLOWED_CABIN_CLASSES = {"Economy", "Premium Economy", "Business", "First"}
CABIN_CLASS_MAP = {
    "economy": "Economy",
    "premium economy": "Premium Economy",
    "premium_economy": "Premium Economy",
    "business": "Business",
    "business class": "Business",
    "first": "First",
    "first class": "First",
}


# ── Cleaning report ───────────────────────────────────────────────────────────

@dataclass
class CleaningReport:
    source: str
    input_count: int = 0
    output_count: int = 0
    dropped_missing_required: int = 0
    dropped_impossible_fare: int = 0
    dropped_duplicates: int = 0
    dropped_invalid_route: int = 0
    corrected_airline: int = 0
    corrected_city: int = 0
    corrected_duration: int = 0
    corrected_cabin_class: int = 0

    @property
    def total_dropped(self) -> int:
        return (
            self.dropped_missing_required
            + self.dropped_impossible_fare
            + self.dropped_duplicates
            + self.dropped_invalid_route
        )

    def summary(self) -> str:
        return (
            f"[{self.source}] in={self.input_count} out={self.output_count} "
            f"dropped={self.total_dropped} "
            f"(missing={self.dropped_missing_required}, "
            f"bad_fare={self.dropped_impossible_fare}, "
            f"dupes={self.dropped_duplicates}, "
            f"bad_route={self.dropped_invalid_route})"
        )


# ── Duration parsing ──────────────────────────────────────────────────────────

def _parse_duration(value) -> Optional[int]:
    """
    Parse duration from various formats to total minutes.
    Handles: "2h 30m", "2:30", 150 (numeric), "150" (string numeric).
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if value > 0:
            return int(value)
        return None
    s = str(value).strip().lower()
    # "Xh Ym" format
    m = re.match(r"(\d+)\s*h\s*(\d+)\s*m", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    # "Xh" only
    m = re.match(r"(\d+)\s*h", s)
    if m:
        return int(m.group(1)) * 60
    # "X:Y" format
    m = re.match(r"(\d+):(\d+)", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    # Plain numeric string
    try:
        v = float(s)
        return int(v) if v > 0 else None
    except ValueError:
        return None


# ── Cabin class normalisation ─────────────────────────────────────────────────

def _normalise_cabin(value: Optional[str]) -> str:
    if not value:
        return "Economy"
    cleaned = str(value).strip().lower()
    return CABIN_CLASS_MAP.get(cleaned, "Economy")


# ── Main cleaning function ────────────────────────────────────────────────────

def clean_fare_records(
    records: list[FareRecord],
    source: str = "unknown",
) -> tuple[list[FareRecord], CleaningReport]:
    """
    Clean a list of FareRecord objects.

    Returns:
        (cleaned_records, report)
    """
    report = CleaningReport(source=source, input_count=len(records))
    cleaned: list[FareRecord] = []
    seen_fingerprints: set[str] = set()

    for rec in records:
        # ── 1. Required fields ────────────────────────────────────────────────
        if not rec.origin or not rec.destination or rec.fare is None:
            report.dropped_missing_required += 1
            continue

        # ── 2. Impossible fare ────────────────────────────────────────────────
        try:
            fare_val = float(rec.fare)
        except (TypeError, ValueError):
            report.dropped_impossible_fare += 1
            continue

        if fare_val < FARE_MIN_INR or fare_val > FARE_MAX_INR:
            report.dropped_impossible_fare += 1
            continue

        rec.fare = round(fare_val, 2)

        # ── 3. Normalise cities ───────────────────────────────────────────────
        orig_origin = rec.origin
        orig_dest = rec.destination
        rec.origin = normalise_city(rec.origin)
        rec.destination = normalise_city(rec.destination)
        if rec.origin != orig_origin or rec.destination != orig_dest:
            report.corrected_city += 1

        if rec.origin == rec.destination:
            report.dropped_invalid_route += 1
            continue

        # ── 4. Normalise airline ──────────────────────────────────────────────
        if rec.airline_code:
            normalised = normalise_airline(rec.airline_code)
            if normalised != rec.airline_code:
                rec.airline_code = normalised
                report.corrected_airline += 1

        # ── 5. Duration to minutes ────────────────────────────────────────────
        parsed_duration = _parse_duration(rec.duration_minutes)
        if parsed_duration != rec.duration_minutes:
            report.corrected_duration += 1
        rec.duration_minutes = parsed_duration

        # ── 6. Clip days_left ─────────────────────────────────────────────────
        if rec.days_left is not None:
            if rec.days_left < 0 or rec.days_left > DAYS_LEFT_MAX:
                rec.days_left = None

        # ── 7. Cabin class ────────────────────────────────────────────────────
        normalised_cabin = _normalise_cabin(rec.cabin_class)
        if normalised_cabin != rec.cabin_class:
            rec.cabin_class = normalised_cabin
            report.corrected_cabin_class += 1

        # ── 8. Time periods ───────────────────────────────────────────────────
        if rec.departure_time:
            rec.departure_time = normalise_time_period(rec.departure_time)
        if rec.arrival_time:
            rec.arrival_time = normalise_time_period(rec.arrival_time)

        # ── 9. Disaggregated fare consistency & Advance Window ───────────────
        if rec.advance_window is None and rec.days_left is not None:
            if rec.days_left <= 1:
                rec.advance_window = "T+1"
            elif rec.days_left <= 7:
                rec.advance_window = "T+7"
            elif rec.days_left <= 15:
                rec.advance_window = "T+15"
            elif rec.days_left <= 30:
                rec.advance_window = "T+30"
            else:
                rec.advance_window = "T+45"

        # Check disaggregation consistency: Base + Taxes + UDF + ConvFee == Total
        if (
            rec.base_fare is not None
            and rec.taxes is not None
            and rec.udf_charge is not None
            and rec.convenience_fee is not None
        ):
            component_sum = round(rec.base_fare + rec.taxes + rec.udf_charge + rec.convenience_fee, 2)
            if abs(component_sum - rec.fare) > 0.05:
                # Re-align taxes to ensure exact balance with total fare
                rec.taxes = round(rec.fare - rec.base_fare - rec.udf_charge - rec.convenience_fee, 2)
        rec.total_fare = rec.fare

        # Exclude sold out or cancelled flights from clean fare basket
        if rec.status and rec.status.upper() in {"SOLD_OUT", "CANCELLED"}:
            report.dropped_impossible_fare += 1
            continue

        # ── 10. Deduplication ─────────────────────────────────────────────────
        fp = rec.fingerprint()
        if fp in seen_fingerprints:
            report.dropped_duplicates += 1
            continue
        seen_fingerprints.add(fp)

        cleaned.append(rec)

    report.output_count = len(cleaned)
    logger.info(report.summary())
    return cleaned, report


def detect_route_window_outliers(
    records: list[FareRecord],
    iqr_multiplier: float = 2.5,
) -> list[FareRecord]:
    """
    Remove extreme statistical fare outliers per route and advance-purchase window
    bucket to prevent artificial distortion of price indices.
    """
    if len(records) < 10:
        return records

    from collections import defaultdict
    import numpy as np

    grouped: dict[tuple[str, str, Optional[str]], list[FareRecord]] = defaultdict(list)
    for r in records:
        key = (r.origin, r.destination, r.advance_window)
        grouped[key].append(r)

    filtered_records: list[FareRecord] = []
    for key, group in grouped.items():
        if len(group) < 5:
            filtered_records.extend(group)
            continue

        fares = np.array([r.fare for r in group], dtype=float)
        q25, q75 = np.percentile(fares, 25), np.percentile(fares, 75)
        iqr = q75 - q25
        lower_bound = max(FARE_MIN_INR, q25 - iqr_multiplier * iqr)
        upper_bound = min(FARE_MAX_INR, q75 + iqr_multiplier * iqr)

        for r in group:
            if lower_bound <= r.fare <= upper_bound:
                filtered_records.append(r)

    return filtered_records
