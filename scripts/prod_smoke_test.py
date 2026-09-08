"""
scripts/prod_smoke_test.py
---------------------------
Performs the ONE real production smoke test against the deployed FareCast API on Render.
Never logs or exposes any secrets.
"""
import requests
import json

def main():
    url = "https://farecast-api.onrender.com/api/live/search"
    params = {
        "origin": "DEL",
        "destination": "BOM",
        "departure_date": "2026-09-20",
        "adults": 1,
        "travel_class": "ECONOMY",
        "persist": "true"
    }

    print(f"[TEST] Invoking ONE real production request to: {url}")
    print(f"[TEST] Params: {params}")

    resp = requests.get(url, params=params, timeout=45)
    print(f"[RESULT] HTTP Status: {resp.status_code}")

    try:
        data = resp.json()
    except Exception as e:
        print(f"[ERROR] Non-JSON response: {resp.text[:300]}")
        return

    print(f"[RESULT] data_mode: {data.get('data_mode')}")
    print(f"[RESULT] source: {data.get('source')}")
    print(f"[RESULT] total: {data.get('total')}")
    print(f"[RESULT] persisted_count: {data.get('persisted_count')}")

    offers = data.get("offers", [])
    if offers:
        first = offers[0]
        print("\n--- Verified Live Flight Offer (Sanitized) ---")
        print(f"Carrier:            {first.get('airline_name')} ({first.get('airline_code')})")
        print(f"Flight Number:      {first.get('flight_number')}")
        print(f"Route:              {first.get('origin')} -> {first.get('destination')}")
        print(f"Departure:          {first.get('departure_datetime')}")
        print(f"Arrival:            {first.get('arrival_datetime')}")
        print(f"Stops:              {first.get('stops')}")
        print(f"Duration Minutes:   {first.get('duration_minutes')}")
        print(f"Cabin Class:        {first.get('cabin_class')}")
        print(f"Fare:               {first.get('fare')} {first.get('currency')}")
        print(f"INR Estimate:       {first.get('fare_inr_estimate')}")
        print(f"Source / Data Mode: {first.get('source')} / {first.get('data_mode')}")

    # Check persistence in database
    print("\n--- Verifying Persistence in FareCast Database ---")
    fares_url = "https://farecast-api.onrender.com/api/fares"
    f_resp = requests.get(fares_url, params={"origin": "DEL", "destination": "BOM", "data_mode": "LIVE"}, timeout=20)
    print(f"Querying /api/fares?origin=DEL&destination=BOM&data_mode=LIVE -> Status: {f_resp.status_code}")
    if f_resp.status_code == 200:
        fdata = f_resp.json()
        print(f"Total LIVE records in DB: {fdata.get('meta', {}).get('total')}")
        if fdata.get('data'):
            sample = fdata.get('data')[0]
            print(f"Sample DB record: ID={sample.get('id')}, Source={sample.get('source')}, Mode={sample.get('data_mode')}, Fare={sample.get('fare')} {sample.get('currency')}, Airline={sample.get('airline_code')}")

if __name__ == "__main__":
    main()
