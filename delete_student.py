
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "attendance.db"

connection = sqlite3.connect(DB_PATH)

student_id = "E"

# Check whether the student exists
student = connection.execute(
    "SELECT student_id, name FROM students WHERE student_id = ?",
    (student_id,)
).fetchone()

if student:
    print(f"Student found: ID {student[0]} | Name: {student[1]}")

    confirm = input("Delete this enrolled student permanently? (yes/no): ")

    if confirm.strip().lower() == "yes":
        # Delete this student's attendance records first
        connection.execute(
            "DELETE FROM attendance WHERE student_id = ?",
            (student_id,)
        )

        # Delete the student's enrollment and face embedding
        connection.execute(
            "DELETE FROM students WHERE student_id = ?",
            (student_id,)
        )

        connection.commit()
        print("Student ID E and its attendance records have been deleted.")
    else:
        print("Deletion cancelled.")
else:
    print("No enrolled student found with ID E.")

connection.close()
