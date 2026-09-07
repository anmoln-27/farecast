import sqlite3

con = sqlite3.connect('farecast.db')
schema = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='fare_observations'").fetchone()
print("SCHEMA:", schema[0] if schema else "NOT FOUND")
count = con.execute("SELECT count(*) FROM fare_observations").fetchone()
print("COUNT:", count[0] if count else 0)
con.close()
