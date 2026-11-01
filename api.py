
from pathlib import Path
from datetime import date
import math
import secrets
import sqlite3
import os

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "attendance.db"

# DEMO ONLY: change this before real deployment.
TEACHER_DEMO_PASSWORD = os.getenv(
    "TEACHER_DEMO_PASSWORD", "teacher123"
)

app = FastAPI(title="Smart Attendance System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*", "Authorization", "Content-Type"],
)

# In-memory demo sessions. Restarting the API logs everyone out.
SESSIONS = {}


class LoginRequest(BaseModel):
    role: str
    student_id: str | None = None
    password: str | None = None


def get_connection():
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Database not found: {DB_PATH}",
        )

    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def current_user(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Please log in.",
        )

    token = authorization.removeprefix("Bearer ").strip()
    user = SESSIONS.get(token)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please log in again.",
        )

    return user


def require_teacher(authorization: str | None):
    user = current_user(authorization)

    if user["role"] != "teacher":
        raise HTTPException(
            status_code=403,
            detail="Teacher access required.",
        )

    return user


@app.get("/")
def home():
    return {
        "message": "Smart Attendance System API is running"
    }


@app.post("/api/login")
def login(payload: LoginRequest):
    role = payload.role.strip().lower()

    if role == "teacher":
        if payload.password != TEACHER_DEMO_PASSWORD:
            raise HTTPException(
                status_code=401,
                detail="Incorrect teacher demo password.",
            )

        user = {
            "role": "teacher",
            "student_id": None,
            "name": "Teacher",
        }

    elif role == "student":
        student_id = (payload.student_id or "").strip()

        if not student_id:
            raise HTTPException(
                status_code=400,
                detail="Enter your student ID.",
            )

        conn = get_connection()

        try:
            student = conn.execute(
                """
                SELECT student_id, name
                FROM students
                WHERE student_id = ?
                """,
                (student_id,),
            ).fetchone()
        finally:
            conn.close()

        if not student:
            raise HTTPException(
                status_code=401,
                detail="Student ID not found.",
            )

        user = {
            "role": "student",
            "student_id": str(student["student_id"]),
            "name": str(student["name"]),
        }

    else:
        raise HTTPException(
            status_code=400,
            detail="Choose Teacher or Student.",
        )

    token = secrets.token_urlsafe(32)
    SESSIONS[token] = user

    return {
        "token": token,
        "user": user,
    }


@app.post("/api/logout")
def logout(
    authorization: str | None = Header(default=None),
):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        SESSIONS.pop(token, None)

    return {"message": "Logged out"}


@app.get("/api/me")
def get_me(
    authorization: str | None = Header(default=None),
):
    return current_user(authorization)


@app.get("/api/stats")
def get_stats(
    authorization: str | None = Header(default=None),
):
    require_teacher(authorization)

    conn = get_connection()

    try:
        today = date.today().isoformat()

        total_students = conn.execute(
            "SELECT COUNT(*) FROM students"
        ).fetchone()[0]

        present_today = conn.execute(
            """
            SELECT COUNT(DISTINCT student_id)
            FROM attendance
            WHERE date = ?
            """,
            (today,),
        ).fetchone()[0]

        return {
            "total_students": total_students,
            "present_today": present_today,
            "attendance_rate": round(
                present_today / total_students * 100, 1
            ) if total_students else 0,
            "date": today,
        }

    finally:
        conn.close()


@app.get("/api/students")
def get_students(
    authorization: str | None = Header(default=None),
):
    require_teacher(authorization)

    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT student_id, name
            FROM students
            ORDER BY name COLLATE NOCASE
            """
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


@app.get("/api/attendance")
def get_attendance(
    authorization: str | None = Header(default=None),
):
    require_teacher(authorization)

    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT id, student_id, name, date, time
            FROM attendance
            ORDER BY date DESC, time DESC, id DESC
            LIMIT 200
            """
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


@app.get("/api/my-attendance")
def get_my_attendance(
    authorization: str | None = Header(default=None),
):
    user = current_user(authorization)

    if user["role"] != "student":
        raise HTTPException(
            status_code=403,
            detail="Student access required.",
        )

    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT id, student_id, name, date, time
            FROM attendance
            WHERE student_id = ?
            ORDER BY date DESC, time DESC, id DESC
            LIMIT 200
            """,
            (user["student_id"],),
        ).fetchall()

        today = date.today().isoformat()

        return {
            "student_id": user["student_id"],
            "name": user["name"],
            "date": today,
            "present_today": any(
                row["date"] == today for row in rows
            ),
            "attendance": [dict(row) for row in rows],
        }

    finally:
        conn.close()


@app.get("/api/my-attendance/percentage")
def get_my_attendance_percentage(
    authorization: str | None = Header(default=None),
):
    user = current_user(authorization)

    if user["role"] != "student":
        raise HTTPException(
            status_code=403,
            detail="Student access required.",
        )

    conn = get_connection()

    try:
        today = date.today().isoformat()

        sessions_held = conn.execute(
            """
            SELECT COUNT(DISTINCT date)
            FROM attendance
            WHERE date <= ?
            """,
            (today,),
        ).fetchone()[0]

        sessions_attended = conn.execute(
            """
            SELECT COUNT(*)
            FROM attendance
            WHERE student_id = ?
              AND date <= ?
            """,
            (user["student_id"], today),
        ).fetchone()[0]

        if sessions_held == 0:
            return {
                "sessions_attended": 0,
                "sessions_held": 0,
                "percentage": None,
                "classes_needed": None,
            }

        percentage = round(sessions_attended / sessions_held * 100, 1)
        raw_needed = (0.75 * sessions_held - sessions_attended) / 0.25
        classes_needed = max(0, math.ceil(raw_needed))

        return {
            "sessions_attended": sessions_attended,
            "sessions_held": sessions_held,
            "percentage": percentage,
            "classes_needed": classes_needed,
        }

    finally:
        conn.close()


# Existing buffer/session inspection endpoints.
# These are teacher-only and do not change attendance marking.

@app.get("/api/buffer/today")
def get_today_buffer(
    authorization: str | None = Header(default=None),
):
    require_teacher(authorization)

    conn = get_connection()

    try:
        today = date.today().isoformat()

        rows = conn.execute(
            """
            SELECT
                p.session_id,
                p.batch_number,
                p.student_id,
                s.name,
                p.first_seen,
                p.last_seen,
                p.confirmation_count,
                p.status
            FROM pending_detections p
            JOIN students s
                ON s.student_id = p.student_id
            JOIN class_sessions c
                ON c.id = p.session_id
            WHERE c.class_date = ?
              AND p.status = 'pending'
            ORDER BY p.batch_number, s.name COLLATE NOCASE
            """,
            (today,),
        ).fetchall()

        return {
            "date": today,
            "pending_count": len(rows),
            "students": [dict(row) for row in rows],
        }

    except sqlite3.OperationalError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Buffer tables unavailable: {exc}",
        )

    finally:
        conn.close()


@app.get("/api/batches/today")
def get_today_batches(
    authorization: str | None = Header(default=None),
):
    require_teacher(authorization)

    conn = get_connection()

    try:
        today = date.today().isoformat()

        rows = conn.execute(
            """
            SELECT
                b.id,
                b.session_id,
                b.batch_number,
                b.status,
                b.teacher_id,
                b.created_at,
                b.finalized_at
            FROM attendance_batches b
            JOIN class_sessions c
                ON c.id = b.session_id
            WHERE c.class_date = ?
            ORDER BY b.batch_number
            """,
            (today,),
        ).fetchall()

        return {
            "date": today,
            "batch_count": len(rows),
            "batches": [dict(row) for row in rows],
        }

    except sqlite3.OperationalError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Batch tables unavailable: {exc}",
        )

    finally:
        conn.close()


@app.get("/api/buffer/summary")
def get_buffer_summary(
    authorization: str | None = Header(default=None),
):
    require_teacher(authorization)

    conn = get_connection()

    try:
        today = date.today().isoformat()

        row = conn.execute(
            """
            SELECT
                COUNT(
                    CASE WHEN p.status = 'pending' THEN 1 END
                ) AS pending_detections,

                COUNT(
                    CASE WHEN p.status = 'finalized' THEN 1 END
                ) AS finalized_detections,

                COUNT(
                    DISTINCT CASE
                        WHEN p.status = 'pending'
                        THEN p.student_id
                    END
                ) AS pending_students

            FROM pending_detections p
            JOIN class_sessions c
                ON c.id = p.session_id
            WHERE c.class_date = ?
            """,
            (today,),
        ).fetchone()

        return {
            "date": today,
            **dict(row),
        }

    except sqlite3.OperationalError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Buffer tables unavailable: {exc}",
        )

    finally:
        conn.close()


# ── Attendance Token (student dispute) ───────────────────

class AttendanceTokenRequest(BaseModel):
    class_date: str   # ISO date string, e.g. "2024-10-15"
    reason: str


def ensure_token_table(conn: sqlite3.Connection):
    """Create the attendance_tokens table if it doesn't exist yet."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance_tokens (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            token_id    TEXT    NOT NULL UNIQUE,
            student_id  TEXT    NOT NULL,
            class_date  TEXT    NOT NULL,
            reason      TEXT    NOT NULL,
            submitted_at TEXT   NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'Pending'
        )
        """
    )
    conn.commit()


@app.post("/api/attendance-token")
def raise_attendance_token(
    payload: AttendanceTokenRequest,
    authorization: str | None = Header(default=None),
):
    user = current_user(authorization)

    if user["role"] != "student":
        raise HTTPException(
            status_code=403,
            detail="Only students can raise attendance tokens.",
        )

    # Validate class_date format (YYYY-MM-DD) and reject future dates.
    from datetime import datetime
    try:
        parsed_date = datetime.strptime(payload.class_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD.",
        )

    if parsed_date > date.today():
        raise HTTPException(
            status_code=400,
            detail="Class date cannot be in the future.",
        )

    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(
            status_code=400,
            detail="Please provide a reason.",
        )
    if len(reason) > 500:
        raise HTTPException(
            status_code=400,
            detail="Reason must be 500 characters or fewer.",
        )

    token_id = secrets.token_hex(8).upper()   # e.g. "A1B2C3D4E5F60708"
    submitted_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        ensure_token_table(conn)

        # Prevent duplicate token for the same student + date.
        existing = conn.execute(
            """
            SELECT id FROM attendance_tokens
            WHERE student_id = ? AND class_date = ?
            """,
            (user["student_id"], payload.class_date),
        ).fetchone()

        if existing:
            raise HTTPException(
                status_code=409,
                detail="You have already raised a token for this date.",
            )

        conn.execute(
            """
            INSERT INTO attendance_tokens
                (token_id, student_id, class_date, reason, submitted_at, status)
            VALUES (?, ?, ?, ?, ?, 'Pending')
            """,
            (
                token_id,
                user["student_id"],
                payload.class_date,
                reason,
                submitted_at,
            ),
        )
        conn.commit()

    finally:
        conn.close()

    return {
        "token_id": token_id,
        "student_id": user["student_id"],
        "class_date": payload.class_date,
        "submitted_at": submitted_at,
        "status": "Pending",
    }


@app.get("/api/my-attendance-tokens")
def get_my_attendance_tokens(
    authorization: str | None = Header(default=None),
):
    """Return all tokens the authenticated student has raised."""
    user = current_user(authorization)

    if user["role"] != "student":
        raise HTTPException(
            status_code=403,
            detail="Student access required.",
        )

    conn = get_connection()
    try:
        ensure_token_table(conn)
        rows = conn.execute(
            """
            SELECT token_id, class_date, reason, submitted_at, status
            FROM attendance_tokens
            WHERE student_id = ?
            ORDER BY submitted_at DESC
            """,
            (user["student_id"],),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ── Teacher notifications ─────────────────────────────────

def ensure_notification_columns(conn: sqlite3.Connection):
    """Add read_at column to attendance_tokens if not present."""
    columns = [
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(attendance_tokens)"
        ).fetchall()
    ]
    if "read_at" not in columns:
        conn.execute(
            "ALTER TABLE attendance_tokens ADD COLUMN read_at TEXT"
        )
        conn.commit()


@app.get("/api/notifications")
def get_notifications(
    authorization: str | None = Header(default=None),
):
    """Return all attendance-token requests as teacher notifications."""
    require_teacher(authorization)

    conn = get_connection()
    try:
        ensure_token_table(conn)
        ensure_notification_columns(conn)

        rows = conn.execute(
            """
            SELECT
                t.token_id,
                t.student_id,
                COALESCE(s.name, t.student_id) AS student_name,
                t.class_date,
                t.reason,
                t.submitted_at,
                t.status,
                t.read_at
            FROM attendance_tokens t
            LEFT JOIN students s ON s.student_id = t.student_id
            ORDER BY t.submitted_at DESC
            """
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


class MarkReadRequest(BaseModel):
    token_ids: list[str]


@app.post("/api/notifications/mark-read")
def mark_notifications_read(
    payload: MarkReadRequest,
    authorization: str | None = Header(default=None),
):
    """Mark the given token_ids as read (sets read_at to now)."""
    require_teacher(authorization)

    if not payload.token_ids:
        return {"updated": 0}

    from datetime import datetime
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        ensure_token_table(conn)
        ensure_notification_columns(conn)

        placeholders = ",".join("?" * len(payload.token_ids))
        conn.execute(
            f"""
            UPDATE attendance_tokens
            SET read_at = ?
            WHERE token_id IN ({placeholders})
              AND read_at IS NULL
            """,
            [now, *payload.token_ids],
        )
        conn.commit()
        return {"updated": conn.total_changes}

    finally:
        conn.close()


# ── Token review: Approve / Reject ───────────────────────

class ReviewTokenRequest(BaseModel):
    action: str   # "approve" or "reject"


@app.post("/api/attendance-token/{token_id}/review")
def review_attendance_token(
    token_id: str,
    payload: ReviewTokenRequest,
    authorization: str | None = Header(default=None),
):
    """
    Approve or reject an attendance token.

    Approve: insert an attendance record for the student on the requested
             class_date (prevents duplicates), then mark token Approved.
    Reject:  mark the token Rejected. No attendance record is created.

    Only an authenticated teacher may call this endpoint.
    The token must exist and be in Pending status.
    """
    require_teacher(authorization)

    action = payload.action.strip().lower()
    if action not in ("approve", "reject"):
        raise HTTPException(
            status_code=400,
            detail="action must be 'approve' or 'reject'.",
        )

    from datetime import datetime

    conn = get_connection()
    try:
        ensure_token_table(conn)
        ensure_notification_columns(conn)

        # Fetch the token row.
        row = conn.execute(
            """
            SELECT t.token_id, t.student_id, t.class_date, t.status,
                   COALESCE(s.name, t.student_id) AS student_name
            FROM attendance_tokens t
            LEFT JOIN students s ON s.student_id = t.student_id
            WHERE t.token_id = ?
            """,
            (token_id,),
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Token not found.",
            )

        if row["status"] != "Pending":
            raise HTTPException(
                status_code=409,
                detail=f"Token is already {row['status']}.",
            )

        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        attendance_inserted = False

        if action == "approve":
            student_id  = row["student_id"]
            class_date  = row["class_date"]
            student_name = row["student_name"]

            # Verify the student still exists in the students table.
            student = conn.execute(
                "SELECT student_id FROM students WHERE student_id = ?",
                (student_id,),
            ).fetchone()
            if not student:
                raise HTTPException(
                    status_code=422,
                    detail="Student no longer exists in the database.",
                )

            # Guard: do not create a duplicate attendance record.
            duplicate = conn.execute(
                """
                SELECT id FROM attendance
                WHERE student_id = ? AND date = ?
                """,
                (student_id, class_date),
            ).fetchone()

            if not duplicate:
                # Insert time as "00:00 (Token)" to distinguish from
                # face-recognition records.
                conn.execute(
                    """
                    INSERT INTO attendance (student_id, name, date, time)
                    VALUES (?, ?, ?, ?)
                    """,
                    (student_id, student_name, class_date, "00:00 (Token)"),
                )
                attendance_inserted = True

            # Update token status to Approved.
            conn.execute(
                """
                UPDATE attendance_tokens
                SET status = 'Approved', read_at = COALESCE(read_at, ?)
                WHERE token_id = ?
                """,
                (now, token_id),
            )

        else:  # reject
            conn.execute(
                """
                UPDATE attendance_tokens
                SET status = 'Rejected', read_at = COALESCE(read_at, ?)
                WHERE token_id = ?
                """,
                (now, token_id),
            )

        conn.commit()

        return {
            "token_id": token_id,
            "status": "Approved" if action == "approve" else "Rejected",
            "attendance_inserted": attendance_inserted,
        }

    finally:
        conn.close()
