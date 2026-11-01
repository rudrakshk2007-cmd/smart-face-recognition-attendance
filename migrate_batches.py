from pathlib import Path
from datetime import datetime
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "attendance.db"

if not DB_PATH.exists():
    sys.exit(f"Database not found: {DB_PATH}")

# Back up the database using SQLite's backup mechanism.
backup_path = ROOT / (
    f"attendance_backup_batches_"
    f"{datetime.now():%Y%m%d_%H%M%S}.db"
)

source = sqlite3.connect(DB_PATH, timeout=10)
backup = sqlite3.connect(backup_path)

try:
    source.backup(backup)
finally:
    backup.close()
    source.close()

print(f"Backup created: {backup_path.name}")

conn = sqlite3.connect(DB_PATH, timeout=10)
conn.row_factory = sqlite3.Row

try:
    # Foreign keys must be disabled before starting the transaction
    # because we are rebuilding the pending_detections table.
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("BEGIN IMMEDIATE")

    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }

    required = {
        "students",
        "attendance",
        "teachers",
        "class_sessions",
        "pending_detections",
    }

    missing = required - tables
    if missing:
        raise RuntimeError(
            "Missing tables: " + ", ".join(sorted(missing))
            + ". Check that the previous setup has completed."
        )

    columns = {
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(pending_detections)"
        )
    }

    if "batch_number" in columns:
        conn.rollback()
        print("Batch migration already appears to be applied.")
        print("No schema changes were made.")
        sys.exit(0)

    # Preserve the current pending rows as legacy batch 1.
    conn.execute("""
        CREATE TABLE attendance_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL
                REFERENCES class_sessions(id),
            batch_number INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            teacher_id TEXT REFERENCES teachers(teacher_id),
            created_at TEXT NOT NULL,
            finalized_at TEXT,
            UNIQUE(session_id, batch_number)
        )
    """)

    sessions = conn.execute(
        "SELECT id FROM class_sessions"
    ).fetchall()

    now = datetime.now().isoformat(timespec="seconds")

    for session in sessions:
        conn.execute(
            """
            INSERT INTO attendance_batches
                (session_id, batch_number, status, created_at)
            VALUES (?, 1, 'legacy', ?)
            """,
            (session["id"], now),
        )

    conn.execute("""
        CREATE TABLE pending_detections_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL
                REFERENCES class_sessions(id),
            student_id TEXT NOT NULL
                REFERENCES students(student_id),
            batch_number INTEGER NOT NULL DEFAULT 1,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            confirmation_count INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'pending',
            finalized_at TEXT,
            UNIQUE(session_id, student_id, batch_number)
        )
    """)

    conn.execute("""
        INSERT INTO pending_detections_new (
            id, session_id, student_id, batch_number,
            first_seen, last_seen, confirmation_count,
            status, finalized_at
        )
        SELECT
            id, session_id, student_id, 1,
            first_seen, last_seen, confirmation_count,
            status, finalized_at
        FROM pending_detections
    """)

    conn.execute("DROP TABLE pending_detections")
    conn.execute("""
        ALTER TABLE pending_detections_new
        RENAME TO pending_detections
    """)

    conn.commit()

    # Re-enable foreign-key enforcement and verify integrity.
    conn.execute("PRAGMA foreign_keys = ON")

    violations = conn.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    if violations:
        raise RuntimeError(
            f"Foreign-key check failed: {len(violations)} violation(s). "
            f"Your backup is available at {backup_path.name}."
        )

    print("Batch migration completed successfully.")
    print("Existing attendance records were not modified.")
    print("Existing pending detections were assigned to legacy batch 1.")

except Exception as exc:
    if conn.in_transaction:
        conn.rollback()

    print(f"Migration failed: {exc}")
    print(f"Backup retained: {backup_path.name}")
    sys.exit(1)

finally:
    conn.close()