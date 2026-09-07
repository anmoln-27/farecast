import sqlite3

con = sqlite3.connect('farecast.db')

print("=" * 60)
print("  FARECAST PRODUCTION DATABASE INVENTORY AUDIT")
print("=" * 60)

total = con.execute('SELECT COUNT(*) FROM fare_observations').fetchone()[0]
print(f"Total Fare Observations:    {total:,}")

sources = con.execute('SELECT source, COUNT(*) FROM fare_observations GROUP BY source').fetchall()
print(f"Sources Breakdown:          {dict(sources)}")

modes = con.execute('SELECT data_mode, COUNT(*) FROM fare_observations GROUP BY data_mode').fetchall()
print(f"Data Modes:                 {dict(modes)}")

date_range = con.execute('SELECT MIN(travel_date), MAX(travel_date) FROM fare_observations').fetchone()
print(f"Date Coverage Range:        {date_range[0]} to {date_range[1]}")

routes_obs = con.execute("SELECT COUNT(DISTINCT origin || '-' || destination) FROM fare_observations").fetchone()[0]
print(f"Distinct Routes Observed:   {routes_obs}")

windows = con.execute('SELECT advance_window, COUNT(*) FROM fare_observations GROUP BY advance_window ORDER BY advance_window').fetchall()
print(f"Advance Windows:            {dict(windows)}")

airlines_obs = con.execute('SELECT COUNT(DISTINCT airline_code) FROM fare_observations').fetchone()[0]
print(f"Distinct Airlines Observed: {airlines_obs}")

index_count = con.execute('SELECT COUNT(*) FROM airfare_index').fetchone()[0]
print(f"Airfare Index Series DB:    {index_count}")

routes_meta = con.execute('SELECT COUNT(*) FROM routes').fetchone()[0]
print(f"Registered Metro Routes:    {routes_meta}")

airlines_meta = con.execute('SELECT COUNT(*) FROM airlines').fetchone()[0]
print(f"Registered Airlines:        {airlines_meta}")

anomalies = con.execute('SELECT COUNT(*) FROM anomalies').fetchone()[0]
print(f"Anomalies Recorded:         {anomalies}")

benchmarks = con.execute('SELECT COUNT(*) FROM dgca_route_fare_benchmarks').fetchone()[0]
print(f"Benchmark Fare Series:      {benchmarks}")

con.close()
print("=" * 60)
