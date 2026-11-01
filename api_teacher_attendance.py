from pathlib import Path
import sqlite3
from datetime import date, datetime, time as dtime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "attendance.db"

app = FastAPI(title="Smart Attendance System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

def get_connection():
    if not DB_PATH.exists():
        raise RuntimeError(f"Database not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

@app.get("/")
def home():
    return {"message": "Smart Attendance System API is running"}

@app.get("/api/stats")
def get_stats():
    conn = get_connection()
    try:
        today = date.today().isoformat()
        total = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        present = conn.execute(
            "SELECT COUNT(DISTINCT student_id) FROM attendance WHERE date = ?", (today,)
        ).fetchone()[0]
        return {
            "total_students": total,
            "present_today": present,
            "attendance_rate": round(present / total * 100, 1) if total else 0,
            "date": today,
        }
    finally:
        conn.close()

@app.get("/api/students")
def get_students():
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT student_id, name FROM students ORDER BY name COLLATE NOCASE"
        ).fetchall()]
    finally:
        conn.close()

@app.get("/api/attendance")
def get_attendance():
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT id, student_id, name, date, time FROM attendance "
            "ORDER BY date DESC, time DESC, id DESC LIMIT 200"
        ).fetchall()]
    finally:
        conn.close()

@app.get("/api/classes/today")
def get_today_class():
    conn = get_connection()
    try:
        today = date.today().isoformat()
        row = conn.execute(
            "SELECT id, subject, class_date, start_time, end_time, status "
            "FROM class_sessions WHERE class_date = ? ORDER BY id DESC LIMIT 1",
            (today,),
        ).fetchone()
        return dict(row) if row else {"message": "No class session created for today"}
    finally:
        conn.close()

@app.get("/api/classes/{session_id}/pending")
def get_pending(session_id: int):
    conn = get_connection()
    try:
        exists = conn.execute("SELECT id FROM class_sessions WHERE id = ?", (session_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Class session not found")
        rows = conn.execute(
            """SELECT p.student_id, s.name, p.first_seen, p.last_seen, p.confirmation_count
               FROM pending_detections p
               JOIN students s ON s.student_id = p.student_id
               WHERE p.session_id = ? AND p.status = 'pending'
               ORDER BY p.first_seen""", (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.get("/api/classes/{session_id}/attendance")
def get_session_attendance(session_id: int):
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT a.id, a.student_id, a.name, a.date, a.time, a.session_id
               FROM attendance a WHERE a.session_id = ?
               ORDER BY a.time, a.name""", (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
