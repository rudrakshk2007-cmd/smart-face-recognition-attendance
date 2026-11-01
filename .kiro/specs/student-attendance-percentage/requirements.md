# Requirements Document

## Introduction

This document specifies requirements for the **Student Attendance Percentage** feature, an enhancement to the existing Smart Face Recognition-Based Attendance System. The feature extends the student-facing "My Attendance" dashboard to display the student's attendance percentage for the single course (Embedded Systems and Architecture), a session count breakdown, a warning when attendance falls below the 75% threshold, and a calculation of how many consecutive additional sessions are needed to reach 75%.

Eligible sessions are determined entirely from the `attendance` table in the existing SQLite database: any distinct date on which at least one student has a recorded attendance entry is treated as a class that was actually held. Future dates are excluded automatically because they can have no records yet. No new tables are created and no existing records are modified.

---

## Glossary

- **API**: The FastAPI backend defined in `api.py` that serves all data to the frontend.
- **Attendance_Calculator**: The server-side logic responsible for computing session counts and attendance percentage.
- **Eligible_Session**: A distinct calendar date (≤ today) present in the `attendance` table for which at least one student has an attendance record, meaning a class was actually held on that date.
- **Sessions_Attended**: The count of Eligible_Sessions on which the authenticated student has a personal attendance record.
- **Sessions_Held**: The total count of Eligible_Sessions across all students.
- **Attendance_Percentage**: `(Sessions_Attended / Sessions_Held) × 100`, rounded to one decimal place.
- **Warning_Threshold**: 75%. Attendance_Percentage below this value triggers a visual warning.
- **Classes_Needed**: The minimum number of consecutive future sessions the student must attend to reach 75%, computed as `max(0, ceil((0.75 × Sessions_Held − Sessions_Attended) / 0.25))`.
- **Student_Dashboard**: The "My Attendance" page rendered in `App.jsx` for authenticated student users.
- **Session**: An in-memory entry in the `SESSIONS` dict keyed by the Bearer token issued at login.
- **Student_ID**: The primary key from the `students` table, bound to the authenticated user's Session and never supplied by the client at query time.

---

## Requirements

### Requirement 1: Secure Student Identity Resolution

**User Story:** As a student, I want my attendance data to be fetched using my authenticated identity, so that I cannot accidentally or intentionally view another student's records.

#### Acceptance Criteria

1. WHEN the API receives a request to the attendance-percentage endpoint, THE API SHALL resolve the student's identity exclusively from the Bearer token in the `Authorization` header by looking up the token in the server-side `SESSIONS` dict.
2. IF the `Authorization` header is absent or the token is not present in `SESSIONS`, THEN THE API SHALL return HTTP 401 with a descriptive error message.
3. IF the authenticated user's role is not `student`, THEN THE API SHALL return HTTP 403 with a descriptive error message.
4. WHEN a request to the attendance-percentage endpoint includes a `student_id` query parameter or body field, THE API SHALL silently ignore that parameter and use only the Student_ID resolved from the token.

---

### Requirement 2: Eligible Session Computation

**User Story:** As a student, I want the system to determine which classes have actually been held, so that my percentage is calculated against real attended sessions only.

#### Acceptance Criteria

1. THE Attendance_Calculator SHALL derive the set of Eligible_Sessions by querying the `attendance` table for all distinct `date` values where at least one row exists, restricted to dates less than or equal to today's date.
2. THE Attendance_Calculator SHALL NOT use the `class_sessions` table as the source of truth for which sessions were held.
3. IF no rows exist in the `attendance` table with a date ≤ today, THEN THE Attendance_Calculator SHALL return a Sessions_Held count of 0.
4. THE Attendance_Calculator SHALL NOT count multiple attendance rows for the same student on the same date as multiple sessions (the existing `UNIQUE(student_id, date)` constraint already prevents this, but the query must not double-count dates regardless).

---

### Requirement 3: Attendance Percentage Calculation

**User Story:** As a student, I want to see my attendance percentage for the course, so that I can track whether I meet the minimum requirement.

#### Acceptance Criteria

1. WHEN Sessions_Held is greater than 0, THE Attendance_Calculator SHALL compute Attendance_Percentage as `round((Sessions_Attended / Sessions_Held) * 100, 1)`.
2. WHEN Sessions_Held is 0, THE Attendance_Calculator SHALL return a null or sentinel value indicating no percentage is available, rather than performing a division that would produce NaN, Infinity, or 0%.
3. THE Attendance_Calculator SHALL compute Sessions_Attended by counting the Eligible_Sessions on which a row exists in the `attendance` table for the authenticated student's Student_ID.
4. THE Attendance_Calculator SHALL compute Classes_Needed as `max(0, ceil((0.75 × Sessions_Held − Sessions_Attended) / 0.25))` when Sessions_Held is greater than 0.
5. WHEN Sessions_Attended equals Sessions_Held and Classes_Needed would be negative, THE Attendance_Calculator SHALL return 0 for Classes_Needed.

---

### Requirement 4: New API Endpoint for Attendance Percentage

**User Story:** As a student, I want the frontend to retrieve my attendance percentage from the server, so that the calculation is always based on up-to-date database records.

#### Acceptance Criteria

1. THE API SHALL expose a new `GET /api/my-attendance/percentage` endpoint accessible only to authenticated student users.
2. WHEN a valid student token is provided, THE API SHALL return a JSON object containing at minimum: `sessions_attended` (integer), `sessions_held` (integer), `percentage` (number or null), and `classes_needed` (integer or null).
3. WHEN Sessions_Held is 0, THE API SHALL return `percentage: null` and `classes_needed: null` in the response body.
4. THE API SHALL use the same `current_user` and role-check pattern already established in `api.py` for the existing `/api/my-attendance` endpoint.
5. THE API SHALL query the database on every request and SHALL NOT cache results in memory, so the displayed value reflects the current state of the `attendance` table.

---

### Requirement 5: Frontend Display of Attendance Percentage

**User Story:** As a student, I want to see my attendance percentage on my dashboard, so that I always know my current standing without navigating elsewhere.

#### Acceptance Criteria

1. WHEN the Student_Dashboard loads, THE Student_Dashboard SHALL fetch data from `GET /api/my-attendance/percentage` using the same `apiFetch` helper and Bearer token already used for `/api/my-attendance`.
2. WHEN Sessions_Held is greater than 0, THE Student_Dashboard SHALL display the attendance in the format `"Attendance: X/Y sessions (Z%)"` where X = Sessions_Attended, Y = Sessions_Held, Z = Attendance_Percentage.
3. WHEN Sessions_Held is 0 (i.e., the API returns `percentage: null`), THE Student_Dashboard SHALL display the message `"Attendance percentage will appear after the first eligible class."` and SHALL NOT display a numeric percentage, NaN, 0%, or Infinity.
4. THE Student_Dashboard SHALL display the attendance percentage information using the existing `stat-card` CSS class so that it integrates visually with the three existing stat-cards on the "My Attendance" page.
5. THE Student_Dashboard SHALL auto-refresh the percentage data on the same 10-second interval already used for the rest of the page, keeping both data fetches in sync.

---

### Requirement 6: Below-Threshold Warning

**User Story:** As a student, I want a visual warning when my attendance falls below 75%, so that I am alerted before it becomes a serious problem.

#### Acceptance Criteria

1. WHEN Attendance_Percentage is less than 75 and Sessions_Held is greater than 0, THE Student_Dashboard SHALL display a red visual warning indicator alongside the attendance percentage.
2. WHEN Attendance_Percentage is exactly 75 or greater, THE Student_Dashboard SHALL NOT display the red warning indicator.
3. WHEN Sessions_Held is 0 (percentage unavailable), THE Student_Dashboard SHALL NOT display the red warning indicator.
4. THE Student_Dashboard SHALL use inline CSS color `#c75b51` (the same red already used for the connection-error dot in `App.jsx`) or an equivalent red from the existing design system for the warning indicator.

---

### Requirement 7: Classes Needed to Reach 75%

**User Story:** As a student, I want to know how many more consecutive sessions I need to attend to reach 75%, so that I can plan my attendance proactively.

#### Acceptance Criteria

1. WHEN Attendance_Percentage is less than 75 and Sessions_Held is greater than 0, THE Student_Dashboard SHALL display the Classes_Needed value in the format `"Attend X more consecutive session(s) to reach 75%."` below the attendance percentage display.
2. WHEN Attendance_Percentage is exactly 75 or greater, THE Student_Dashboard SHALL NOT display the Classes_Needed message.
3. WHEN Sessions_Held is 0, THE Student_Dashboard SHALL NOT display the Classes_Needed message.
4. THE Student_Dashboard SHALL derive the Classes_Needed value from the `classes_needed` field in the API response and SHALL NOT recompute it on the client side.

---

### Requirement 8: Preservation of Existing Features

**User Story:** As a student or teacher, I want all existing functionality to remain unchanged, so that the new feature does not break anything already working.

#### Acceptance Criteria

1. THE API SHALL continue to serve `GET /api/my-attendance` with its existing response shape unchanged after the new endpoint is added.
2. THE Student_Dashboard SHALL continue to display the three existing stat-cards (Student name/ID, Today's status, Total records) in their current positions.
3. THE API SHALL continue to serve all teacher-only endpoints (`/api/stats`, `/api/students`, `/api/attendance`, `/api/buffer/today`, `/api/batches/today`, `/api/buffer/summary`) without modification.
4. THE API SHALL NOT modify, delete, or overwrite any rows in the `attendance`, `students`, or `class_sessions` tables as a side effect of serving the new endpoint.
5. THE Student_Dashboard SHALL NOT change the existing navigation structure, colour scheme, typography, sidebar, or topbar layout.
