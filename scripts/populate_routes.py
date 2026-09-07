import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.db.base import SessionLocal
from backend.app.db.models import Route, FareObservation

CITY_NAMES = {
    "DEL": "Delhi",
    "BOM": "Mumbai",
    "BLR": "Bengaluru",
    "CCU": "Kolkata",
    "HYD": "Hyderabad",
    "MAA": "Chennai",
    "GOI": "Goa",
    "PNQ": "Pune",
    "AMD": "Ahmedabad",
}

DISTANCES = {
    ("DEL", "BOM"): 1148.0, ("BOM", "DEL"): 1148.0,
    ("DEL", "BLR"): 1740.0, ("BLR", "DEL"): 1740.0,
    ("DEL", "CCU"): 1305.0, ("CCU", "DEL"): 1305.0,
    ("DEL", "HYD"): 1253.0, ("HYD", "DEL"): 1253.0,
    ("DEL", "MAA"): 1760.0, ("MAA", "DEL"): 1760.0,
    ("BOM", "BLR"): 842.0,  ("BLR", "BOM"): 842.0,
    ("BOM", "CCU"): 1654.0, ("CCU", "BOM"): 1654.0,
    ("BOM", "HYD"): 621.0,  ("HYD", "BOM"): 621.0,
    ("BOM", "MAA"): 1033.0, ("MAA", "BOM"): 1033.0,
    ("BLR", "CCU"): 1560.0, ("CCU", "BLR"): 1560.0,
    ("BLR", "HYD"): 500.0,  ("HYD", "BLR"): 500.0,
    ("BLR", "MAA"): 290.0,  ("MAA", "BLR"): 290.0,
    ("CCU", "HYD"): 1180.0, ("HYD", "CCU"): 1180.0,
    ("CCU", "MAA"): 1366.0, ("MAA", "CCU"): 1366.0,
    ("HYD", "MAA"): 510.0,  ("MAA", "HYD"): 510.0,
    ("BOM", "GOI"): 435.0,  ("GOI", "BOM"): 435.0,
    ("DEL", "PNQ"): 1173.0, ("PNQ", "DEL"): 1173.0,
}

session = SessionLocal()()
obs_routes = session.query(FareObservation.origin, FareObservation.destination).distinct().all()
added = 0
for orig, dest in obs_routes:
    if not orig or not dest:
        continue
    existing = session.query(Route).filter_by(origin=orig, destination=dest).first()
    if not existing:
        dist = DISTANCES.get((orig, dest), 1000.0)
        session.add(Route(
            origin=orig,
            destination=dest,
            origin_city=CITY_NAMES.get(orig, orig),
            destination_city=CITY_NAMES.get(dest, dest),
            distance_km=dist,
            is_domestic=True
        ))
        added += 1

session.commit()
total = session.query(Route).count()
print(f"Added {added} routes. Total routes in DB: {total}")
session.close()
