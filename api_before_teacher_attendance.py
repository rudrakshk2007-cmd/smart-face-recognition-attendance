
from pathlib import Path
import sqlite3
from datetime import date

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "attendance.db"

app = FastAPI(title="Smart Attendance System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_connection():
    if not DB_PATH.exists():
        raise RuntimeError(f"Database not found: {DB_PATH}")

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


@app.get("/")
def home():
    return {"message": "Smart Attendance System API is running"}


@app.get("/api/stats")
def get_stats():
    connection = get_connection()

    try:
        today = date.today().isoformat()

        total_students = connection.execute(
            "SELECT COUNT(*) FROM students"
        ).fetchone()[0]

        present_today = connection.execute(
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
        connection.close()


@app.get("/api/students")
def get_students():
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT student_id, name
            FROM students
            ORDER BY name COLLATE NOCASE
            """
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        connection.close()


@app.get("/api/attendance")
def get_attendance():
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT id, student_id, name, date, time
            FROM attendance
            ORDER BY date DESC, time DESC, id DESC
            LIMIT 200
            """
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        connection.close()
