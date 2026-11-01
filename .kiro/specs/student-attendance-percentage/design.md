# Design Document

## Overview

This enhancement adds a `GET /api/my-attendance/percentage` endpoint to `api.py` and a fourth stat-card to the student "My Attendance" page in `App.jsx`. No new tables, no schema migrations, and no changes to existing endpoints or the face-recognition flow.

---

## Architecture

### Backend change — one new endpoint in `api.py`

Append a new route after the existing `/api/my-attendance` handler. It reuses the same `current_user()` / role-check pattern already present in the file.

```
GET /api/my-attendance/percentage
Authorization: Bearer <token>   (student role required)

Response 200:
{
  "sessions_attended": int,
  "sessions_held":     int,
  "percentage":        float | null,   // null when sessions_held == 0
  "classes_needed":    int   | null    // null when sessions_held == 0
}

Response 401: token missing / invalid
Response 403: role != "student"
```

**SQL queries used (no writes, no table changes):**

```sql
-- Sessions_Held: distinct dates ≤ today where ANY student has a record
SELECT COUNT(DISTINCT date)
FROM   attendance
WHERE  date <= :today

-- Sessions_Attended: how many of those dates the authenticated student attended
SELECT COUNT(*)
FROM   attendance
WHERE  student_id = :student_id
  AND  date <= :today
```

Both queries run inside a single `get_connection()` / `conn.close()` block with no caching.

**Calculation logic (pure Python, no new imports needed):**

```python
import math

sessions_held     = <result of first query>
sessions_attended = <result of second query>

if sessions_held == 0:
    percentage     = None
    classes_needed = None
else:
    percentage     = round(sessions_attended / sessions_held * 100, 1)
    raw_needed     = (0.75 * sessions_held - sessions_attended) / 0.25
    classes_needed = max(0, math.ceil(raw_needed))
```

`math` is already part of the Python standard library; no new dependency.

---

### Frontend change — fourth stat-card in `App.jsx`

**New state variable** (added alongside `myData`, `attendance`, etc.):

```js
const [pctData, setPctData] = useState(null);
```

**Fetch added inside `loadData()`** for the student branch, in parallel with the existing `/api/my-attendance` call:

```js
// student branch inside loadData()
const [data, pct] = await Promise.all([
  apiFetch("/api/my-attendance", token),
  apiFetch("/api/my-attendance/percentage", token),
]);
setMyData(data);
setAttendance(data.attendance || []);
setPctData(pct);
```

This keeps both fetches on the same 10-second interval automatically.

**New stat-card** inserted as the fourth card in the existing `stats-grid` section (after the three current cards), using the identical `stat-card` CSS class:

```jsx
<article className="stat-card">
  <p>Attendance</p>

  <h2 style={{ fontSize: pctData?.percentage !== null ? 26 : 14 }}>
    {loading
      ? "…"
      : pctData?.percentage !== null && pctData?.percentage !== undefined
        ? `${pctData.sessions_attended}/${pctData.sessions_held}`
        : "—"}
  </h2>

  <span className="stat-note"
    style={{ color: pctData?.percentage !== null && pctData?.percentage < 75
               ? "#c75b51" : undefined }}>
    {loading
      ? ""
      : pctData === null
        ? "Fetching…"
        : pctData.percentage === null
          ? "Attendance percentage will appear after the first eligible class."
          : `${pctData.percentage}%${pctData.percentage < 75
              ? " ⚠ Below 75%" : ""}`}
  </span>

  {/* Classes-needed line — only shown when below threshold */}
  {!loading && pctData?.percentage !== null && pctData?.percentage < 75 && (
    <p style={{ marginTop: 8, fontSize: 10, color: "#c75b51" }}>
      Attend {pctData.classes_needed} more consecutive session(s) to reach 75%.
    </p>
  )}
</article>
```

The `stats-grid` CSS is `grid-template-columns: repeat(3, minmax(0, 1fr))` — adding a fourth card causes it to wrap on a second row naturally on small screens. To keep four cards on one row on desktop we update the grid rule only for the student "My Attendance" context:

```css
/* App.css — additive only */
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

The teacher "My Overview" `stats-grid` keeps the existing three-column layout unchanged.

---

## File change summary

| File | Change type | Description |
|------|-------------|-------------|
| `api.py` | Additive | Append `GET /api/my-attendance/percentage` after the existing `/api/my-attendance` handler; add `import math` at top |
| `frontend/src/App.jsx` | Additive | New `pctData` state; parallel fetch in student branch of `loadData`; fourth stat-card in the "My Attendance" section; add `stats-grid--four` class to the student stats-grid |
| `frontend/src/App.css` | Additive | `.stats-grid--four` responsive rule (8 lines) |

No database migrations. No changes to existing endpoints. No changes to teacher views.

---

## Requirements traceability

| Requirement | Satisfied by |
|-------------|-------------|
| R1 — Secure identity | `current_user()` + role check in new endpoint; `student_id` never read from request |
| R2 — Eligible session computation | `SELECT COUNT(DISTINCT date) FROM attendance WHERE date <= :today` |
| R3 — Calculation | Python `math.ceil` formula; `None` guard when `sessions_held == 0` |
| R4 — New endpoint | `GET /api/my-attendance/percentage` |
| R5 — Frontend display | Fourth stat-card; `apiFetch` helper; parallel fetch in `loadData` |
| R6 — Below-threshold warning | `#c75b51` colour on stat-note when `percentage < 75` |
| R7 — Classes needed | Server-computed `classes_needed` displayed below percentage |
| R8 — Preservation | Existing endpoints untouched; three teacher/student cards unchanged; no DB writes |
