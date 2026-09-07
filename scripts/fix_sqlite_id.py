import sqlite3

con = sqlite3.connect('farecast.db')
con.execute("PRAGMA foreign_keys=OFF")

# Check current columns
cols = con.execute("PRAGMA table_info(fare_observations)").fetchall()
col_names = [c[1] for c in cols if c[1] != 'id']

create_sql = f"""
CREATE TABLE fare_observations_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source VARCHAR(50) NOT NULL,
    data_mode VARCHAR(10) NOT NULL,
    airline_code VARCHAR(10),
    flight_number VARCHAR(20),
    origin VARCHAR(10) NOT NULL,
    destination VARCHAR(10) NOT NULL,
    travel_date DATE NOT NULL,
    booking_date DATE,
    departure_time VARCHAR(20),
    arrival_time VARCHAR(20),
    stops INTEGER,
    duration_minutes INTEGER,
    cabin_class VARCHAR(15),
    fare FLOAT NOT NULL,
    currency VARCHAR(5) DEFAULT 'INR',
    collected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    days_left INTEGER,
    base_fare FLOAT,
    taxes FLOAT,
    udf_charge FLOAT,
    convenience_fee FLOAT,
    total_fare FLOAT,
    advance_window VARCHAR(10),
    status VARCHAR(20) DEFAULT 'AVAILABLE',
    FOREIGN KEY(airline_code) REFERENCES airlines (code)
);
"""

con.execute(create_sql)

cols_str = ", ".join(col_names)
con.execute(f"INSERT INTO fare_observations_new ({cols_str}) SELECT {cols_str} FROM fare_observations")

con.execute("DROP TABLE fare_observations")
con.execute("ALTER TABLE fare_observations_new RENAME TO fare_observations")

# Create essential indexes
con.execute("CREATE INDEX ix_fare_obs_source ON fare_observations (source)")
con.execute("CREATE INDEX ix_fare_obs_data_mode ON fare_observations (data_mode)")
con.execute("CREATE INDEX ix_fare_obs_airline ON fare_observations (airline_code)")
con.execute("CREATE INDEX ix_fare_obs_origin ON fare_observations (origin)")
con.execute("CREATE INDEX ix_fare_obs_dest ON fare_observations (destination)")
con.execute("CREATE INDEX ix_fare_obs_travel_date ON fare_observations (travel_date)")
con.execute("CREATE INDEX ix_fare_obs_advance_window ON fare_observations (advance_window)")
con.execute("CREATE INDEX ix_fare_obs_days_left ON fare_observations (days_left)")
con.execute("CREATE INDEX ix_fare_obs_route_date ON fare_observations (origin, destination, travel_date)")
con.execute("CREATE INDEX ix_fare_obs_route_window ON fare_observations (origin, destination, advance_window)")

con.execute("PRAGMA foreign_keys=ON")
con.commit()

count = con.execute("SELECT count(*) FROM fare_observations").fetchone()[0]
print("Migrated successfully. New count:", count)
schema = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='fare_observations'").fetchone()[0]
print("New schema:\n", schema)
con.close()
