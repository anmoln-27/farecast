import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

endpoints = [
    ("Health", "/health"),
    ("Dashboard Summary", "/api/dashboard/summary"),
    ("Routes", "/api/routes"),
    ("Airlines", "/api/airlines"),
    ("Fares List", "/api/fares?limit=5"),
    ("Lead-Time Elasticity", "/api/fares/elasticity"),
    ("Sector Heatmap Matrix", "/api/fares/sector-matrix"),
    ("Airfare Index", "/api/index"),
    ("ML Prediction", "/api/prediction?origin=DEL&destination=BOM&airline=IndiGo&cabin_class=Economy&days_left=15"),
    ("Anomalies", "/api/anomalies"),
    ("DGCA Context", "/api/dgca"),
    ("CPI Reference", "/api/cpi"),
    ("NSO APIx Monthly", "/api/v1/nso/apix?frequency=monthly"),
    ("RBI Macro Feed", "/api/v1/rbi/macro-feed"),
    ("30-Day Backtest Results", "/api/v1/analytics/backtest-results"),
]

print("=" * 80)
print("  FARECAST FULL PLATFORM ENDPOINT SMOKE TEST")
print("=" * 80)

all_passed = True
for name, path in endpoints:
    try:
        resp = client.get(path)
        if resp.status_code == 200:
            print(f"[PASS] {name:<25} ({path}) -> Status 200 OK")
        else:
            print(f"[FAIL] {name:<25} ({path}) -> Status {resp.status_code}: {resp.text[:120]}")
            all_passed = False
    except Exception as exc:
        print(f"[ERROR] {name:<25} ({path}) -> Exception: {exc}")
        all_passed = False

print("=" * 80)
if all_passed:
    print("ALL PLATFORM ENDPOINTS VERIFIED & FUNCTIONAL!")
else:
    print("SOME ENDPOINTS FAILED VERIFICATION.")
print("=" * 80)
