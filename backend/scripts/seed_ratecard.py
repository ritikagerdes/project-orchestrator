#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data.sqlite"

CANONICAL = {
    "Software Developer": 80.0,
    "Senior Software Developer": 120.0,
    "Software Architect": 150.0,
    "WordPress Developer": 70.0,
    "Project Manager": 95.0,
    "Cloud Architect / DevOps Engineer": 140.0
}

def main():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    # ensure table exists (schema name from your models)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rate_card (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      role TEXT UNIQUE NOT NULL,
      rate REAL NOT NULL
    )
    """)
    # remove any roles not in canonical, and upsert canonical values
    cur.execute("SELECT role FROM rate_card")
    existing = {r[0] for r in cur.fetchall()}
    for role in existing - set(CANONICAL.keys()):
        cur.execute("DELETE FROM rate_card WHERE role = ?", (role,))
    for role, rate in CANONICAL.items():
        cur.execute("INSERT INTO rate_card(role, rate) VALUES(?, ?) ON CONFLICT(role) DO UPDATE SET rate=excluded.rate", (role, rate))
    conn.commit()
    # print final table
    cur.execute("SELECT role, rate FROM rate_card ORDER BY role")
    for r in cur.fetchall():
        print(r)
    conn.close()

if __name__ == "__main__":
    main()