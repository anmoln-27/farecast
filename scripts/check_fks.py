import sqlite3

con = sqlite3.connect('farecast.db')
tables = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("TABLES:", [t[0] for t in tables])

for t in tables:
    name = t[0]
    fks = con.execute(f"PRAGMA foreign_key_list({name})").fetchall()
    if fks:
        print(f"FKs in {name}:", fks)
con.close()
