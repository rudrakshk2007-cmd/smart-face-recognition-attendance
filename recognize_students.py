"""Multi-face student recognition and attendance.

Run from the project root:
    python recognize_students.py

Controls in the webcam window:
    E = enroll one student (follow terminal prompts)
    V = print today's attendance
    Q = quit

Uses YuNet for detection and SFace for embeddings. The laptop performs
recognition; an ESP32 can be added separately over serial later.
"""
from pathlib import Path
import sqlite3
import sys
import time
from datetime import datetime

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "attendance.db"
DETECTOR_PATH = ROOT / "models" / "face_detection_yunet_2023mar.onnx"
CAMERA_INDEX = 0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
COSINE_THRESHOLD = 0.363  # OpenCV SFace commonly uses 0.363 as a starting point
CONFIRM_FRAMES = 5
MIN_FACE_SIZE = 80  # pixels wide/high; smaller faces are harder to match reliably


def find_sface_model():
    candidates = list((ROOT / "models").rglob("*.onnx"))
    candidates = [p for p in candidates if "sface" in p.name.lower() or "face_recognition" in str(p).lower()]
    if not candidates:
        # Fallback: any ONNX file whose filename suggests SFace/recognition.
        candidates = [p for p in (ROOT / "models").rglob("*.onnx") if "recogn" in p.name.lower()]
    return candidates[0] if candidates else None


def open_database():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS students (
        student_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        embedding BLOB NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        name TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        UNIQUE(student_id, date)
    )""")
    conn.commit()
    return conn


def load_students(conn):
    rows = conn.execute("SELECT student_id, name, embedding FROM students").fetchall()
    known = []
    for row in rows:
        try:
            embedding = np.frombuffer(row["embedding"], dtype=np.float32).copy()
            if embedding.size:
                norm = np.linalg.norm(embedding)
                if norm:
                    embedding /= norm
                    known.append((str(row["student_id"]), str(row["name"]), embedding))
        except (TypeError, ValueError):
            print(f"Warning: could not read embedding for {row['student_id']}; skipping it.")
    return known


def get_embedding(recognizer, frame, face):
    aligned = recognizer.alignCrop(frame, face)
    feature = recognizer.feature(aligned)
    vector = np.asarray(feature, dtype=np.float32).reshape(-1)
    norm = np.linalg.norm(vector)
    if norm == 0:
        return None
    return vector / norm


def match_student(embedding, known_students):
    best = None
    best_score = -1.0
    for student_id, name, known_embedding in known_students:
        if embedding.shape != known_embedding.shape:
            continue
        score = float(np.dot(embedding, known_embedding) /
                      (max(np.linalg.norm(embedding), 1e-12) * max(np.linalg.norm(known_embedding), 1e-12)))
        if score > best_score:
            best_score = score
            best = (student_id, name)
    if best is not None and best_score >= COSINE_THRESHOLD:
        return best[0], best[1], best_score
    return None, "Unknown", best_score


def record_attendance(conn, student_id, name):
    now = datetime.now()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO attendance (student_id, name, date, time) VALUES (?, ?, ?, ?)",
            (student_id, name, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")),
        )
        conn.commit()
        return conn.execute("SELECT changes()").fetchone()[0] == 1
    except sqlite3.Error as exc:
        print(f"Could not record attendance: {exc}")
        return False


def print_today_attendance(conn):
    today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT student_id, name, date, time FROM attendance WHERE date = ? ORDER BY time",
        (today,),
    ).fetchall()
    print(f"\nAttendance for {today} ({len(rows)} students)")
    print("-" * 55)
    for row in rows:
        print(f"{row['student_id']} | {row['name']} | {row['time']}")
    print()


def enroll_student(conn, detector, recognizer, frame):
    """Enroll the largest visible face. Existing student IDs are updated."""
    detector.setInputSize((frame.shape[1], frame.shape[0]))
    _, faces = detector.detect(frame)
    if faces is None or len(faces) == 0:
        print("No face detected. Face the camera with good lighting and try again.")
        return
    # Enroll the largest face to avoid accidentally enrolling a bystander.
    face = max(faces, key=lambda f: float(f[2] * f[3]))
    if min(float(face[2]), float(face[3])) < MIN_FACE_SIZE:
        print("Face is too small. Move closer to the camera and try again.")
        return
    student_id = input("Enter student ID: ").strip()
    name = input("Enter student name: ").strip()
    if not student_id or not name:
        print("Student ID and name cannot be empty.")
        return
    try:
        embedding = get_embedding(recognizer, frame, face)
    except cv2.error as exc:
        print(f"Could not create face embedding: {exc}")
        return
    if embedding is None:
        print("Could not create a valid embedding. Try again.")
        return
    try:
        conn.execute(
            "INSERT INTO students (student_id, name, embedding) VALUES (?, ?, ?) "
            "ON CONFLICT(student_id) DO UPDATE SET name=excluded.name, embedding=excluded.embedding",
            (student_id, name, embedding.astype(np.float32).tobytes()),
        )
        conn.commit()
        print(f"Enrolled/updated {name} ({student_id}).")
    except sqlite3.Error as exc:
        print(f"Enrollment failed: {exc}")


def main():
    if not DETECTOR_PATH.exists():
        print(f"YuNet model not found: {DETECTOR_PATH}")
        print("Check that models/face_detection_yunet_2023mar.onnx exists.")
        sys.exit(1)
    sface_path = find_sface_model()
    if sface_path is None:
        print("SFace ONNX model not found under the models/ folder.")
        print("Place your SFace recognition ONNX model in models/ and try again.")
        sys.exit(1)

    try:
        detector = cv2.FaceDetectorYN.create(
            str(DETECTOR_PATH), "", (320, 320), 0.7, 0.3, 5000
        )
        recognizer = cv2.FaceRecognizerSF.create(str(sface_path), "")
    except cv2.error as exc:
        print(f"Could not load OpenCV face models: {exc}")
        print("Check that opencv-contrib-python is installed in your virtual environment.")
        sys.exit(1)

    conn = open_database()
    known_students = load_students(conn)
    print(f"Loaded {len(known_students)} enrolled student(s).")
    print(f"YuNet: {DETECTOR_PATH.relative_to(ROOT)}")
    print(f"SFace: {sface_path.relative_to(ROOT)}")
    print("Controls: E = enroll | V = view today's attendance | Q = quit")

    camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW if sys.platform.startswith("win") else 0)
    if not camera.isOpened():
        camera.release()
        camera = cv2.VideoCapture(CAMERA_INDEX)
    if not camera.isOpened():
        conn.close()
        print("Could not open webcam. Close other camera apps and check camera permissions.")
        sys.exit(1)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

    # Per-student streak counters, so one face doesn't reset another face's streak.
    streaks = {}
    confirmed_today = set()
    today = datetime.now().strftime("%Y-%m-%d")
    already = conn.execute("SELECT student_id FROM attendance WHERE date = ?", (today,)).fetchall()
    confirmed_today.update(str(row[0]) for row in already)
    last_seen = {}
    last_message = "Ready"

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                print("Could not read a frame from the webcam.")
                break

            height, width = frame.shape[:2]
            detector.setInputSize((width, height))
            _, faces = detector.detect(frame)
            visible_ids = set()

            if faces is not None:
                # Process each detected face independently.
                for face in faces:
                    x, y, w, h = [int(round(v)) for v in face[:4]]
                    x = max(0, x); y = max(0, y)
                    w = min(w, width - x); h = min(h, height - y)
                    if w <= 0 or h <= 0:
                        continue

                    if min(w, h) < MIN_FACE_SIZE:
                        label = "Face too small"
                        color = (0, 165, 255)
                        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                        cv2.putText(frame, label, (x, max(25, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                        continue

                    try:
                        embedding = get_embedding(recognizer, frame, face)
                    except cv2.error:
                        continue
                    if embedding is None:
                        continue
                    student_id, name, score = match_student(embedding, known_students)

                    if student_id is None:
                        label = "Unknown"
                        color = (0, 0, 255)
                    else:
                        visible_ids.add(student_id)
                        streaks[student_id] = streaks.get(student_id, 0) + 1
                        last_seen[student_id] = time.time()
                        if streaks[student_id] >= CONFIRM_FRAMES and student_id not in confirmed_today:
                            inserted = record_attendance(conn, student_id, name)
                            confirmed_today.add(student_id)
                            if inserted:
                                last_message = f"Attendance marked: {name} ({student_id})"
                                print(last_message)
                            else:
                                last_message = f"Already marked today: {name}"
                        color = (0, 200, 0)
                        status = "Marked" if student_id in confirmed_today else f"Confirming {min(streaks[student_id], CONFIRM_FRAMES)}/{CONFIRM_FRAMES}"
                        label = f"{name} ({student_id}) - {status}"

                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                    cv2.putText(frame, label, (x, max(25, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)

            # Reset streaks for students not seen in this frame, avoiding stale confirmations.
            for sid in list(streaks):
                if sid not in visible_ids:
                    streaks[sid] = 0

            cv2.rectangle(frame, (0, 0), (width, 62), (25, 30, 35), -1)
            cv2.putText(frame, f"MULTI-FACE ATTENDANCE | Enrolled: {len(known_students)}", (14, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (245, 245, 245), 2)
            cv2.putText(frame, "E: Enroll   V: View attendance   Q: Quit", (14, 49), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 220, 220), 1)
            cv2.imshow("Smart Attendance - Multi Face Recognition", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), ord('Q')):
                break
            elif key in (ord('v'), ord('V')):
                print_today_attendance(conn)
            elif key in (ord('e'), ord('E')):
                # Pause the capture loop while reading enrollment details in the terminal.
                enroll_student(conn, detector, recognizer, frame)
                known_students = load_students(conn)
                streaks.clear()
                print(f"Reloaded {len(known_students)} enrolled student(s).")
    finally:
        camera.release()
        cv2.destroyAllWindows()
        conn.close()
        print("Recognition stopped.")


if __name__ == "__main__":
    main()
