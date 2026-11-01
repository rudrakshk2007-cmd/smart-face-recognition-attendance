"""Run once before starting the updated backend. Makes a timestamped backup first."""
from pathlib import Path
import shutil
import sqlite3
from datetime import datetime

ROOT = Path(__file__).resolve().parent
DB = ROOT / "attendance.db"
if not DB.exists():
    raise SystemExit(f"Database not found: {DB}")

backup = ROOT / f"attendance_backup_before_teacher_feature_{datetime.now():%Y%m%d_%H%M%S}.db"
shutil.copy2(DB, backup)
print(f"Backup created: {backup.name}")

conn = sqlite3.connect(DB)
try:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS teachers (
        teacher_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        embedding BLOB NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS class_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        class_date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        created_at TEXT NOT NULL,
        UNIQUE(subject, class_date)
    );
    CREATE TABLE IF NOT EXISTS pending_detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL REFERENCES class_sessions(id),
        student_id TEXT NOT NULL REFERENCES students(student_id),
        first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL,
        confirmation_count INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'pending',
        finalized_at TEXT,
        UNIQUE(session_id, student_id)
    );
    """)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(attendance)")}
    if "session_id" not in cols:
        conn.execute("ALTER TABLE attendance ADD COLUMN session_id INTEGER REFERENCES class_sessions(id)")
    conn.commit()
    print("Migration complete. Existing student and attendance rows were preserved.")
    print("Note: legacy attendance rows have session_id=NULL; they remain visible in the existing dashboard.")
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()
