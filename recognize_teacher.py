
"""
Smart Attendance System - Demonstration Mode

Controls:
    E = Enroll a student
    T = Enroll/update teacher
    R = Recognize teacher (independent demo; does not affect attendance)
    V = View today's attendance
    Q = Quit

Registered students are marked present automatically after recognition
for the required number of consecutive frames. Class-time restrictions
and teacher finalization are disabled for this demonstration.
"""

from pathlib import Path
from datetime import datetime, date
import sqlite3
import sys
import time

import cv2
import numpy as np


# ---------------- CONFIGURATION ----------------

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "attendance.db"
MODEL_DIR = ROOT / "models"

DETECTOR_PATH = MODEL_DIR / "face_detection_yunet_2023mar.onnx"

CAMERA_INDEX = 0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

COSINE_THRESHOLD = 0.363
CONFIRM_FRAMES = 5
MIN_FACE_SIZE = 80


# ---------------- DATABASE ----------------

def connect_db():
    if not DB_PATH.exists():
        raise RuntimeError(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row

    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }

    if "students" not in tables or "attendance" not in tables:
        conn.close()
        raise RuntimeError(
            "The database must contain students and attendance tables."
        )

    student_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(students)")
    }
    attendance_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(attendance)")
    }

    required_students = {"student_id", "name", "embedding"}
    required_attendance = {"student_id", "name", "date", "time"}

    if not required_students.issubset(student_columns):
        conn.close()
        raise RuntimeError(
            "The students table does not have the expected columns."
        )

    if not required_attendance.issubset(attendance_columns):
        conn.close()
        raise RuntimeError(
            "The attendance table does not have the expected columns."
        )

    # Separate teacher face storage. This does not change student/attendance tables.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            teacher_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            embedding BLOB NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def mark_attendance(conn, student_id, name):
    """Save one attendance record per student per day."""
    now = datetime.now()

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(attendance)")
    }

    try:
        if "session_id" in columns:
            # Use a current session ID only if a session already exists.
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }

            session_id = None

            if "class_sessions" in tables:
                session = conn.execute(
                    """
                    SELECT id FROM class_sessions
                    WHERE class_date = ?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (now.strftime("%Y-%m-%d"),),
                ).fetchone()

                if session:
                    session_id = session["id"]

            conn.execute(
                """
                INSERT OR IGNORE INTO attendance
                    (student_id, name, date, time, session_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    name,
                    now.strftime("%Y-%m-%d"),
                    now.strftime("%H:%M:%S"),
                    session_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT OR IGNORE INTO attendance
                    (student_id, name, date, time)
                VALUES (?, ?, ?, ?)
                """,
                (
                    student_id,
                    name,
                    now.strftime("%Y-%m-%d"),
                    now.strftime("%H:%M:%S"),
                ),
            )

        conn.commit()

        # Check whether a record exists for this student today.
        row = conn.execute(
            """
            SELECT time FROM attendance
            WHERE student_id = ? AND date = ?
            ORDER BY id DESC LIMIT 1
            """,
            (student_id, now.strftime("%Y-%m-%d")),
        ).fetchone()

        if row:
            print(
                f"ATTENDANCE RECORDED: {name} ({student_id}) "
                f"| {now.strftime('%Y-%m-%d')} {row['time']}"
            )
            return True

        print(f"Attendance was not saved for {name}.")
        return False

    except sqlite3.Error as exc:
        conn.rollback()
        print(f"Database error while marking attendance: {exc}")
        return False


def print_today_attendance(conn):
    today = date.today().isoformat()

    rows = conn.execute(
        """
        SELECT student_id, name, date, time
        FROM attendance
        WHERE date = ?
        ORDER BY time, id
        """,
        (today,),
    ).fetchall()

    print(f"\nAttendance for {today} ({len(rows)} records)")
    print("-" * 60)

    if not rows:
        print("No attendance records for today.")

    for row in rows:
        print(
            f"{row['student_id']} | {row['name']} | {row['time']}"
        )

    print("-" * 60)


# ---------------- FACE MODELS ----------------

def find_sface_model():
    if not MODEL_DIR.exists():
        return None

    candidates = list(MODEL_DIR.rglob("*.onnx"))

    preferred = [
        path for path in candidates
        if "sface" in path.name.lower()
        or "face_recognition" in path.name.lower()
    ]

    if not preferred:
        preferred = [
            path for path in candidates
            if "recogn" in path.name.lower()
        ]

    return preferred[0] if preferred else None


def get_embedding(recognizer, frame, face):
    aligned = recognizer.alignCrop(frame, face)
    feature = recognizer.feature(aligned)

    vector = np.asarray(feature, dtype=np.float32).reshape(-1)
    norm = np.linalg.norm(vector)

    if norm <= 0:
        return None

    return vector / norm


def largest_face(faces):
    if faces is None or len(faces) == 0:
        return None

    return max(faces, key=lambda face: float(face[2] * face[3]))


def load_students(conn):
    known_faces = []

    rows = conn.execute(
        "SELECT student_id, name, embedding FROM students"
    ).fetchall()

    for row in rows:
        try:
            vector = np.frombuffer(
                row["embedding"], dtype=np.float32
            ).copy()

            norm = np.linalg.norm(vector)

            if vector.size and norm > 0:
                known_faces.append(
                    (
                        str(row["student_id"]),
                        str(row["name"]),
                        vector / norm,
                    )
                )

        except (TypeError, ValueError):
            print(
                f"Warning: invalid face data for {row['name']}."
            )

    return known_faces


def match_embedding(embedding, known_faces):
    best_match = None
    best_score = -1.0

    for student_id, name, known_embedding in known_faces:
        if embedding.shape != known_embedding.shape:
            continue

        score = float(np.dot(embedding, known_embedding))

        if score > best_score:
            best_match = (student_id, name)
            best_score = score

    if best_match and best_score >= COSINE_THRESHOLD:
        return best_match[0], best_match[1], best_score

    return None, "Unknown", best_score


# ---------------- TEACHER RECOGNITION ----------------

def load_teachers(conn):
    known_faces = []
    rows = conn.execute(
        "SELECT teacher_id, name, embedding FROM teachers"
    ).fetchall()

    for row in rows:
        try:
            vector = np.frombuffer(row["embedding"], dtype=np.float32).copy()
            norm = np.linalg.norm(vector)
            if vector.size and norm > 0:
                known_faces.append((
                    str(row["teacher_id"]),
                    str(row["name"]),
                    vector / norm,
                ))
        except (TypeError, ValueError):
            print(f"Warning: invalid teacher face data for {row['name']}.")

    return known_faces


def enroll_teacher(conn, detector, recognizer, frame):
    """Enroll a teacher in a separate table; never changes student attendance."""
    detector.setInputSize((frame.shape[1], frame.shape[0]))
    _, faces = detector.detect(frame)
    face = largest_face(faces)

    if face is None:
        print("No face detected. Please face the camera and press T again.")
        return

    if min(float(face[2]), float(face[3])) < MIN_FACE_SIZE:
        print("Face too small. Move closer to the camera and try again.")
        return

    teacher_id = input("Enter teacher ID (e.g. TEACHER-01): ").strip()
    name = input("Enter teacher name: ").strip()
    if not teacher_id or not name:
        print("Teacher ID and name cannot be empty.")
        return

    try:
        embedding = get_embedding(recognizer, frame, face)
        if embedding is None:
            print("Could not create a teacher face embedding.")
            return

        conn.execute(
            """
            INSERT INTO teachers (teacher_id, name, embedding, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(teacher_id) DO UPDATE SET
                name = excluded.name,
                embedding = excluded.embedding,
                created_at = excluded.created_at
            """,
            (
                teacher_id,
                name,
                embedding.astype(np.float32).tobytes(),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
        print(f"TEACHER ENROLLED: {name} ({teacher_id})")
        print("Teacher data saved separately. Student attendance was not changed.")
    except (sqlite3.Error, cv2.error) as exc:
        conn.rollback()
        print(f"Teacher enrollment failed: {exc}")


def match_teacher_embedding(embedding, known_faces):
    return match_embedding(embedding, known_faces)


# ---------------- STUDENT ENROLLMENT ----------------

def enroll_student(conn, detector, recognizer, frame):
    detector.setInputSize((frame.shape[1], frame.shape[0]))
    _, faces = detector.detect(frame)

    face = largest_face(faces)

    if face is None:
        print("No face detected. Please try again.")
        return

    if min(float(face[2]), float(face[3])) < MIN_FACE_SIZE:
        print("Face too small. Move closer to the camera.")
        return

    student_id = input("Enter student ID: ").strip()
    name = input("Enter student name: ").strip()

    if not student_id or not name:
        print("Student ID and name cannot be empty.")
        return

    try:
        embedding = get_embedding(recognizer, frame, face)

        if embedding is None:
            print("Could not create a face embedding.")
            return

        conn.execute(
            """
            INSERT INTO students (student_id, name, embedding)
            VALUES (?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                name = excluded.name,
                embedding = excluded.embedding
            """,
            (
                student_id,
                name,
                embedding.astype(np.float32).tobytes(),
            ),
        )

        conn.commit()
        print(f"Student saved: {name} ({student_id})")

    except (sqlite3.Error, cv2.error) as exc:
        conn.rollback()
        print(f"Enrollment failed: {exc}")


# ---------------- MAIN RECOGNITION ----------------

def main():
    if not DETECTOR_PATH.exists():
        raise RuntimeError(
            f"YuNet model not found: {DETECTOR_PATH}"
        )

    sface_path = find_sface_model()

    if sface_path is None:
        raise RuntimeError(
            f"SFace ONNX model not found under: {MODEL_DIR}"
        )

    detector = cv2.FaceDetectorYN.create(
        str(DETECTOR_PATH),
        "",
        (320, 320),
        0.8,
        0.3,
        5000,
    )

    recognizer = cv2.FaceRecognizerSF.create(
        str(sface_path), ""
    )

    conn = connect_db()
    camera = None

    try:
        known_students = load_students(conn)
        known_teachers = load_teachers(conn)
        teacher_scan_mode = False
        teacher_scan_streak = 0
        teacher_success_message = ""
        teacher_success_until = 0.0

        if not known_students:
            print("No enrolled students found. Press E to enroll one.")

        camera = cv2.VideoCapture(CAMERA_INDEX)

        if not camera.isOpened():
            raise RuntimeError(
                "Could not open webcam. Check camera permissions."
            )

        camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

        streaks = {}
        recorded_this_streak = set()

        print("\nSmart Attendance System - DEMO MODE")
        print("E = Enroll student | T = Enroll teacher | R = Recognize teacher")
        print("V = View today's attendance | Q = Quit")
        print(f"Loaded {len(known_students)} enrolled student(s).")
        print(f"Loaded {len(known_teachers)} enrolled teacher(s).")
        print("Attendance time restriction: DISABLED")
        print("Teacher finalization: DISABLED\n")

        while True:
            ok, frame = camera.read()

            if not ok:
                print("Could not read webcam frame.")
                break

            detector.setInputSize(
                (frame.shape[1], frame.shape[0])
            )
            _, faces = detector.detect(frame)

            present_ids = set()

            # Teacher scan mode is independent: skip student recognition and
            # attendance writes until the scan succeeds or is cancelled.
            if teacher_scan_mode:
                teacher_scan_streak = 0 if faces is None else teacher_scan_streak
                if faces is not None:
                    for face in faces:
                        x, y, w, h = map(int, face[:4])
                        if min(w, h) < MIN_FACE_SIZE:
                            continue
                        try:
                            embedding = get_embedding(recognizer, frame, face)
                        except cv2.error:
                            continue
                        if embedding is None:
                            continue

                        teacher_id, teacher_name, score = match_teacher_embedding(
                            embedding, known_teachers
                        )
                        if teacher_id:
                            teacher_scan_streak += 1
                            color = (0, 200, 0)
                            label = f"Teacher: {teacher_name} ({score:.2f})"
                            if teacher_scan_streak >= CONFIRM_FRAMES:
                                teacher_success_message = (
                                    f"TEACHER RECOGNIZED SUCCESSFULLY: "
                                    f"{teacher_name} ({teacher_id})"
                                )
                                print("\n" + "=" * 65)
                                print(teacher_success_message)
                                print("Student attendance was not changed.")
                                print("=" * 65 + "\n")
                                teacher_success_until = time.time() + 3.0
                                teacher_scan_mode = False
                                teacher_scan_streak = 0
                            else:
                                label = f"Teacher match {teacher_scan_streak}/{CONFIRM_FRAMES}: {teacher_name}"
                        else:
                            color = (0, 0, 255)
                            label = "Teacher not recognized"

                        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                        cv2.putText(
                            frame, label, (x, max(25, y - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
                        )
                        break  # Check only the largest visible face in teacher mode.

                cv2.putText(
                    frame,
                    "TEACHER SCAN MODE - Q/Esc to cancel",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 220, 255), 2,
                )
                cv2.imshow("Smart Attendance System - Demo", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    teacher_scan_mode = False
                    teacher_scan_streak = 0
                    print("Teacher recognition cancelled. Attendance was not changed.")
                    if key == ord("q"):
                        break
                continue

            if faces is not None:
                for face in faces:
                    x, y, w, h = map(int, face[:4])

                    if min(w, h) < MIN_FACE_SIZE:
                        continue

                    try:
                        embedding = get_embedding(
                            recognizer, frame, face
                        )
                    except cv2.error:
                        continue

                    if embedding is None:
                        continue

                    student_id, name, score = match_embedding(
                        embedding, known_students
                    )

                    if student_id:
                        present_ids.add(student_id)
                        streaks[student_id] = (
                            streaks.get(student_id, 0) + 1
                        )

                        color = (0, 200, 0)

                        if (
                            streaks[student_id] >= CONFIRM_FRAMES
                            and student_id not in recorded_this_streak
                        ):
                            saved = mark_attendance(
                                conn, student_id, name
                            )

                            if saved:
                                recorded_this_streak.add(student_id)

                            label = f"{name} - PRESENT"
                        else:
                            label = f"{name} ({score:.2f})"

                    else:
                        color = (0, 0, 255)
                        label = "Unknown"

                    cv2.rectangle(
                        frame,
                        (x, y),
                        (x + w, y + h),
                        color,
                        2,
                    )

                    cv2.putText(
                        frame,
                        label,
                        (x, max(25, y - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        color,
                        2,
                    )

            # Allow a later re-scan, but the database prevents a
            # duplicate attendance row for the same day.
            for student_id in list(streaks):
                if student_id not in present_ids:
                    streaks.pop(student_id, None)
                    recorded_this_streak.discard(student_id)

            if time.time() < teacher_success_until:
                cv2.putText(
                    frame, "TEACHER RECOGNIZED SUCCESSFULLY!",
                    (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 200, 0), 2,
                )

            cv2.putText(
                frame,
                "E: Enroll student | T: Enroll teacher | R: Recognize teacher | V: Attendance | Q: Quit",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

            cv2.imshow("Smart Attendance System - Demo", frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            elif key == ord("e"):
                enroll_student(
                    conn, detector, recognizer, frame
                )
                known_students = load_students(conn)
                streaks.clear()
                recorded_this_streak.clear()

            elif key == ord("t"):
                enroll_teacher(conn, detector, recognizer, frame)
                known_teachers = load_teachers(conn)
                print(f"Loaded {len(known_teachers)} enrolled teacher(s).")

            elif key == ord("r"):
                known_teachers = load_teachers(conn)
                if not known_teachers:
                    print("No teacher enrolled yet. Press T to enroll a teacher first.")
                else:
                    teacher_scan_mode = True
                    teacher_scan_streak = 0
                    print("Teacher recognition started. Look at the camera.")
                    print("Press Q or Esc in the webcam window to cancel.")

            elif key == ord("v"):
                print_today_attendance(conn)

    finally:
        if camera is not None:
            camera.release()

        cv2.destroyAllWindows()
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, sqlite3.Error, ValueError, cv2.error) as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)
