import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parent / "attendance.db"
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()

for t in tables:
    name = t["name"]
    schema = conn.execute(
        f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (name,)
    ).fetchone()["sql"]
    print(f"\n=== {name} ===")
    print(schema)
    count = conn.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
    print(f"  rows: {count}")
    if count:
        sample = conn.execute(f"SELECT * FROM [{name}] LIMIT 2").fetchall()
        for row in sample:
            print("  sample:", dict(row))

conn.close()
