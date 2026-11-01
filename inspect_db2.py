import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parent / "attendance.db"
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

print("=== ATTENDANCE RECORDS ===")
rows = conn.execute(
    "SELECT student_id, name, date, time, session_id FROM attendance ORDER BY date, student_id"
).fetchall()
for r in rows:
    print(dict(r))

print("\n=== CLASS SESSIONS ===")
rows = conn.execute(
    "SELECT * FROM class_sessions ORDER BY class_date"
).fetchall()
for r in rows:
    print(dict(r))

print("\n=== DISTINCT ATTENDANCE DATES ===")
rows = conn.execute(
    "SELECT date, COUNT(DISTINCT student_id) as students FROM attendance GROUP BY date ORDER BY date"
).fetchall()
for r in rows:
    print(dict(r))

conn.close()
