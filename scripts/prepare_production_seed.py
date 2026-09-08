"""
scripts/prepare_production_seed.py
----------------------------------
Extracts the genuine 30,114 historical observations and associated
analytical tables from farecast.db into a compressed package
data/historical_observations.json.gz for production database import.
"""
import sqlite3
import gzip
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main():
    db_path = ROOT / "farecast.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # 1. Genuine historical observations
    obs = conn.execute("""
        SELECT 
            source, data_mode, airline_code, flight_number, origin, destination,
            travel_date, booking_date, departure_time, arrival_time, stops,
            duration_minutes, cabin_class, fare, currency, collected_at, created_at,
            days_left, base_fare, taxes, udf_charge, convenience_fee, total_fare,
            advance_window, status
        FROM fare_observations
        WHERE source IN ('kaggle', 'github_full_fare')
        ORDER BY id ASC
    """).fetchall()
    print(f"Extracted {len(obs)} genuine historical observations.")

    # 2. Airfare index records
    indices = conn.execute("""
        SELECT 
            route, airline, period, period_type, avg_fare, baseline_fare,
            index_value, baseline_period, observation_count, weight,
            weight_source, data_source, calculated_at, frequency,
            index_formula, sub_index, dgca_weight
        FROM airfare_index
        ORDER BY id ASC
    """).fetchall()
    print(f"Extracted {len(indices)} index records.")

    # 3. DGCA aviation stats
    dgca = conn.execute("""
        SELECT 
            period, airline, origin, destination, passengers,
            flights_operated, seats_offered, load_factor, data_source, notes, created_at
        FROM dgca_aviation_stats
        ORDER BY id ASC
    """).fetchall()
    print(f"Extracted {len(dgca)} DGCA records.")

    package = {
        "metadata": {
            "total_observations": len(obs),
            "total_indices": len(indices),
            "total_dgca": len(dgca),
            "sources": ["kaggle", "github_full_fare"],
            "data_mode": "HISTORICAL"
        },
        "observations": [dict(r) for r in obs],
        "indices": [dict(r) for r in indices],
        "dgca": [dict(r) for r in dgca],
    }

    out_path = ROOT / "data" / "historical_observations.json.gz"
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        json.dump(package, f)

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"Successfully wrote package to {out_path} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    main()
