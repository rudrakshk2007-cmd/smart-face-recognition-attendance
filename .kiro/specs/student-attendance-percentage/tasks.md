# Implementation Plan

## Task 1: Add GET /api/my-attendance/percentage endpoint to api.py

- [x] 1.1 Add `import math` to the imports section at the top of `api.py` (only if not already present)
- [x] 1.2 Append the new `GET /api/my-attendance/percentage` route after the existing `/api/my-attendance` handler
  - Use `current_user(authorization)` to resolve the student identity from the Bearer token
  - Return HTTP 403 if `user["role"] != "student"`
  - Open a DB connection with `get_connection()`, always close it in a `finally` block
  - Query 1: `SELECT COUNT(DISTINCT date) FROM attendance WHERE date <= ?` with today's ISO date → `sessions_held`
  - Query 2: `SELECT COUNT(*) FROM attendance WHERE student_id = ? AND date <= ?` → `sessions_attended`
  - If `sessions_held == 0`: return `{"sessions_attended": 0, "sessions_held": 0, "percentage": None, "classes_needed": None}`
  - Else: `percentage = round(sessions_attended / sessions_held * 100, 1)`, `classes_needed = max(0, math.ceil((0.75 * sessions_held - sessions_attended) / 0.25))`
  - Return `{"sessions_attended": sessions_attended, "sessions_held": sessions_held, "percentage": percentage, "classes_needed": classes_needed}`
- [ ] 1.3 Verify the existing `/api/my-attendance` handler is unchanged (read it back and confirm its response shape is intact)

## Task 2: Add pctData state and parallel fetch to App.jsx

- [~] 2.1 Add `const [pctData, setPctData] = useState(null);` alongside the other state declarations in the `App` component
- [~] 2.2 In the `loadData` function, replace the student branch's single `apiFetch("/api/my-attendance", token)` call with a `Promise.all` that fetches both `/api/my-attendance` and `/api/my-attendance/percentage` in parallel
  - Store results: `setMyData(data)`, `setAttendance(data.attendance || [])`, `setPctData(pct)`
- [~] 2.3 In the `logout` function, reset `pctData` to `null` alongside the other state resets
- [~] 2.4 Verify the teacher branch of `loadData` is unchanged

## Task 3: Add the fourth stat-card to the student "My Attendance" section in App.jsx

- [~] 3.1 Locate the `stats-grid` section inside `{!isTeacher && activePage === "My Attendance" && (...)}` in `App.jsx`
- [~] 3.2 Add class `stats-grid--four` to the `<section className="stats-grid">` element in that student section only (teacher Overview section keeps its existing class)
- [~] 3.3 Append a fourth `<article className="stat-card">` after the existing three cards with:
  - Label `<p>Attendance</p>`
  - `<h2>` showing `X/Y` (sessions_attended/sessions_held) when percentage is available, or `"—"` when not; font-size 26px when data available, fallback smaller size for the dash
  - `<span className="stat-note">` showing:
    - `""` while loading
    - `"Fetching…"` when `pctData === null` (initial state before first fetch)
    - `"Attendance percentage will appear after the first eligible class."` when `pctData.percentage === null`
    - `"Z%"` (e.g. `"80.0%"`) when at or above 75% — normal muted colour
    - `"Z% ⚠ Below 75%"` when below 75% — colour `#c75b51`
  - Below the stat-note, a conditional `<p>` showing `"Attend X more consecutive session(s) to reach 75%."` in `#c75b51` only when `pctData?.percentage < 75` and `pctData?.percentage !== null`

## Task 4: Add .stats-grid--four CSS rule to App.css

- [~] 4.1 Append the following rules to the end of `App.css` (additive only, do not modify existing rules):
  ```css
  .stats-grid.stats-grid--four {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  @media (max-width: 900px) {
    .stats-grid.stats-grid--four {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  @media (max-width: 500px) {
    .stats-grid.stats-grid--four {
      grid-template-columns: 1fr;
    }
  }
  ```
- [~] 4.2 Confirm existing `.stats-grid` rule (3-column teacher layout) is not modified

## Task 5: End-to-end verification

- [~] 5.1 Start the FastAPI backend and confirm `GET /api/my-attendance/percentage` returns valid JSON for a student token (use curl or the Swagger UI at `/docs`)
- [~] 5.2 Start the Vite frontend dev server and confirm the fourth stat-card appears on the student "My Attendance" page with correct values
- [~] 5.3 Verify the three existing teacher stat-cards on the Overview page are unaffected
- [~] 5.4 Verify the existing `/api/my-attendance` response shape is unchanged
- [~] 5.5 Confirm the red warning and "classes needed" text appear correctly when percentage < 75%, and are absent when percentage >= 75%
