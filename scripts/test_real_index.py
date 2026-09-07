import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date
from backend.app.db.base import SessionLocal
from backend.app.db.models import AirfareIndex

session = SessionLocal()()
rows = session.query(AirfareIndex).all()
print(f"Total AirfareIndex records in DB: {len(rows)}")
for r in rows:
    if r.route == "AGGREGATE":
        print(f"AGGREGATE: sub_index={r.sub_index}, period={r.period}, index_value={r.index_value}, avg_fare={r.avg_fare}, count={r.observation_count}")
session.close()
