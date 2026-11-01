
import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parent / "attendance.db"
conn = sqlite3.connect(db_path)

cursor = conn.execute(
    "DELETE FROM attendance WHERE student_id = ? AND name = ?",
    ("E", "Rudraksh")
)

conn.commit()

if cursor.rowcount > 0:
    print("Successfully deleted Rudraksh (ID E) attendance!")
else:
    print("No attendance record found for Rudraksh (ID E).")

conn.close()
