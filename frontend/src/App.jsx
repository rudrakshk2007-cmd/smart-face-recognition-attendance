
import { useEffect, useRef, useState } from "react";
import "./App.css";

/**
 * Attaches an IntersectionObserver to the returned ref.
 * When the element enters the viewport, adds the class "is-visible".
 * The element must already have the class "reveal" (set in JSX) so
 * it starts in its hidden state via CSS.
 */
function useScrollReveal() {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add("is-visible");
          obs.unobserve(el);
        }
      },
      { threshold: 0.08 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return ref;
}

/**
 * Wrapper that applies scroll-reveal to any element.
 * Renders the child element with a forwarded ref so the
 * IntersectionObserver can attach to the real DOM node.
 */
function Reveal({ as: Tag = "div", className = "", style, children, ...props }) {
  const ref = useScrollReveal();
  return (
    <Tag ref={ref} className={`reveal ${className}`} style={style} {...props}>
      {children}
    </Tag>
  );
}

/**
 * Animates a numeric value from its previous value to target.
 * - Only animates when target actually changes.
 * - Skips animation when prefers-reduced-motion is set.
 * - Returns the display value (number).
 */
function useCountUp(target, duration = 600) {
  const [display, setDisplay] = useState(target);
  const prevRef = useRef(target);
  const rafRef = useRef(null);

  useEffect(() => {
    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    const from = prevRef.current;
    prevRef.current = target;

    // Nothing to animate
    if (from === target || target == null || reducedMotion) {
      setDisplay(target);
      return;
    }

    const start = performance.now();
    const diff = target - from;

    function tick(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(from + diff * eased));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      }
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);

  return display;
}

/**
 * Renders a stat value with:
 * - Skeleton shimmer on initial load (loading=true AND no prior data)
 * - Animated counter on value changes
 * - Plain text fallback for non-numeric values (e.g. "80.0%")
 */
function StatValue({ value, loading, suffix = "", style }) {
  const isInitialLoad = loading && value == null;
  const numericValue = typeof value === "number" ? value : null;
  const animated = useCountUp(numericValue ?? 0);

  if (isInitialLoad) {
    return <span className="stat-skeleton" />;
  }

  if (numericValue !== null) {
    return (
      <span style={style}>
        {animated}
        {suffix}
      </span>
    );
  }

  // Non-numeric or null — render as-is
  return <span style={style}>{value ?? "—"}</span>;
}

/**
 * Small toast notification. Auto-dismisses after `duration` ms.
 */
function Toast({ message, onDone }) {
  useEffect(() => {
    const id = setTimeout(onDone, 3200);
    return () => clearTimeout(id);
  }, [onDone]);

  return (
    <div className="toast-notification" role="status" aria-live="polite">
      <span className="toast-dot" />
      {message}
    </div>
  );
}

const API = "http://127.0.0.1:8000";
const CLASS_TITLE = "Embedded Systems and Architecture";
const TEACHER_DEMO_PASSWORD = "teacher123";

const WEEKLY_SCHEDULE = {
  0: null,
  1: null,
  2: { label: "10:00 AM – 11:00 AM", type: "class" },
  3: { label: "03:50 PM – 05:30 PM", type: "lab" },
  4: { label: "11:00 AM – 11:50 AM", type: "class" },
  5: { label: "08:00 AM – 09:00 AM", type: "class" },
  6: null,
};

// How many minutes before class start the attendance buffer opens.
const BUFFER_MINUTES = 10;

/**
 * Parse a label like "10:00 AM – 11:00 AM" and return a Date object
 * for the start time on today's date, or null if parsing fails.
 */
function parseScheduleStart(label) {
  if (!label) return null;
  // Take the part before the dash separator (handles "–" en-dash)
  const startPart = label.split(/[–-]/)[0].trim();
  // Match "H:MM AM/PM" or "HH:MM AM/PM"
  const match = startPart.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
  if (!match) return null;

  let hours = parseInt(match[1], 10);
  const minutes = parseInt(match[2], 10);
  const meridiem = match[3].toUpperCase();

  if (meridiem === "PM" && hours !== 12) hours += 12;
  if (meridiem === "AM" && hours === 12) hours = 0;

  const now = new Date();
  return new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
    hours,
    minutes,
    0,
    0
  );
}

function BufferCountdown() {
  const [tick, setTick] = useState(0);

  // Re-render every second
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const now = new Date();
  const todaySchedule = WEEKLY_SCHEDULE[now.getDay()];

  if (!todaySchedule) {
    return (
      <div className="buffer-countdown buffer-countdown--none">
        <p className="eyebrow">ATTENDANCE BUFFER</p>
        <p className="buffer-countdown-msg">No class scheduled today.</p>
      </div>
    );
  }

  const classStart = parseScheduleStart(todaySchedule.label);
  if (!classStart) {
    return (
      <div className="buffer-countdown buffer-countdown--none">
        <p className="eyebrow">ATTENDANCE BUFFER</p>
        <p className="buffer-countdown-msg">Schedule time unavailable.</p>
      </div>
    );
  }

  const bufferOpen = new Date(classStart.getTime() - BUFFER_MINUTES * 60 * 1000);
  const secsUntilBuffer = Math.floor((bufferOpen - now) / 1000);
  const secsUntilClass  = Math.floor((classStart - now) / 1000);

  // Format MM:SS or HHhMMmSSs for longer durations
  function fmt(totalSecs) {
    if (totalSecs <= 0) return "0s";
    const h = Math.floor(totalSecs / 3600);
    const m = Math.floor((totalSecs % 3600) / 60);
    const s = totalSecs % 60;
    if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`;
    if (m > 0) return `${m}m ${String(s).padStart(2, "0")}s`;
    return `${s}s`;
  }

  function fmtTime(date) {
    return date.toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    });
  }

  let state, statusText, statusClass;

  if (secsUntilBuffer > 0) {
    state = "upcoming";
    statusText = `Attendance opens in ${fmt(secsUntilBuffer)}`;
    statusClass = "buffer-countdown--upcoming";
  } else if (secsUntilClass > 0) {
    state = "open";
    statusText = "Attendance buffer is open";
    statusClass = "buffer-countdown--open";
  } else {
    state = "started";
    statusClass = "buffer-countdown--started";
  }

  return (
    <div className={`buffer-countdown ${statusClass}`}>
      <div className="buffer-countdown-header">
        <p className="eyebrow">ATTENDANCE BUFFER</p>
        <span className={`buffer-countdown-badge buffer-badge--${state}`}>
          {state === "upcoming" ? "Upcoming" : state === "open" ? "Buffer Open" : "In Progress"}
        </span>
      </div>

      <p className="buffer-countdown-class">{CLASS_TITLE}</p>

      <p className="buffer-countdown-msg">{statusText}</p>

      <div className="buffer-countdown-meta">
        <span>Class starts · {fmtTime(classStart)}</span>
        <span>Buffer opens · {fmtTime(bufferOpen)}</span>
      </div>
    </div>
  );
}

function formatDate(dateString) {
  if (!dateString) return "—";

  return new Date(`${dateString}T00:00:00`).toLocaleDateString(
    "en-IN",
    {
      day: "numeric",
      month: "long",
      year: "numeric",
      weekday: "long",
    }
  );
}

async function apiFetch(path, token) {
  const response = await fetch(`${API}${path}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Request failed.");
  }

  return response.json();
}

function LoginPage({ onLogin }) {
  const [role, setRole] = useState("teacher");
  const [studentId, setStudentId] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setMessage("");

    try {
      const payload =
        role === "teacher"
          ? { role, password }
          : {
              role,
              student_id: studentId.trim(),
            };

      const response = await fetch(`${API}/api/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || "Login failed.");
      }

      onLogin(data.token, data.user);
    } catch (error) {
      setMessage(
        error.message || "Cannot connect to the backend."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={styles.loginShell}>
      <div style={styles.loginGlow} />

      <div style={styles.loginCard}>
        <div style={styles.brandMark}>SA</div>

        <p style={styles.kicker}>
          SMART RECOGNITION / PORTAL
        </p>

        <h1 style={styles.loginTitle}>Welcome back.</h1>

        <p style={styles.loginSubtitle}>
          Sign in to access your attendance workspace.
        </p>

        <div style={styles.roleSwitch}>
          <button
            type="button"
            style={
              role === "teacher"
                ? styles.roleActive
                : styles.roleButton
            }
            onClick={() => {
              setRole("teacher");
              setMessage("");
            }}
          >
            Teacher
          </button>

          <button
            type="button"
            style={
              role === "student"
                ? styles.roleActive
                : styles.roleButton
            }
            onClick={() => {
              setRole("student");
              setMessage("");
            }}
          >
            Student
          </button>
        </div>

        <form
          onSubmit={submit}
          style={{ display: "grid", gap: 16 }}
        >
          {role === "teacher" ? (
            <label style={styles.fieldLabel}>
              Demo password

              <input
                style={styles.loginInput}
                type="password"
                value={password}
                onChange={(event) =>
                  setPassword(event.target.value)
                }
                placeholder="Enter teacher password"
                autoComplete="current-password"
                required
              />
            </label>
          ) : (
            <label style={styles.fieldLabel}>
              Student ID

              <input
                style={styles.loginInput}
                value={studentId}
                onChange={(event) =>
                  setStudentId(event.target.value)
                }
                placeholder="Enter your registered student ID"
                autoComplete="username"
                required
              />
            </label>
          )}

          {message && (
            <div style={styles.errorMessage}>
              {message}
            </div>
          )}

          <button
            style={styles.loginSubmit}
            disabled={busy}
          >
            {busy
              ? "Signing in…"
              : `Continue as ${role}`}
          </button>
        </form>

        <div style={styles.loginFoot}>
          {role === "teacher" ? (
            <>
              Demo password:{" "}
              <strong>{TEACHER_DEMO_PASSWORD}</strong>
            </>
          ) : (
            <>
              Use a student ID already enrolled in the system.
            </>
          )}
        </div>

        <p style={styles.copyright}>
          LOCAL ATTENDANCE SYSTEM · VIT DEMO
        </p>
      </div>
    </div>
  );
}

/**
 * Form that lets a student raise an attendance dispute token.
 * Props:
 *   token      — bearer token from session
 *   onSuccess  — called with the server response after a successful submission
 */
function RaiseTokenForm({ token: authToken, onSuccess }) {
  const today = new Date().toISOString().slice(0, 10);

  const [classDate, setClassDate] = useState(today);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(null); // holds the response

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);

    try {
      const response = await fetch(`${API}/api/attendance-token`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ class_date: classDate, reason: reason.trim() }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || "Submission failed.");
      }

      setSubmitted(data);
      setReason("");
      if (onSuccess) onSuccess(data);
    } catch (err) {
      setError(err.message || "Cannot connect to the server.");
    } finally {
      setBusy(false);
    }
  }

  if (submitted) {
    return (
      <div className="token-success">
        <div className="token-success-icon">✓</div>
        <h3>Token raised successfully</h3>
        <p>
          Your request has been recorded. Share the token ID with your
          teacher if asked.
        </p>
        <div className="token-id-display">
          <span className="eyebrow">TOKEN ID</span>
          <strong>{submitted.token_id}</strong>
        </div>
        <div className="token-meta">
          <span>Date: {submitted.class_date}</span>
          <span>Status: {submitted.status}</span>
          <span>Submitted: {submitted.submitted_at} UTC</span>
        </div>
        <button
          className="text-button"
          style={{ marginTop: 16 }}
          onClick={() => setSubmitted(null)}
        >
          Raise another token
        </button>
      </div>
    );
  }

  return (
    <form className="token-form" onSubmit={handleSubmit}>
      <div className="token-form-row">
        <label className="token-label">
          <span className="eyebrow">CLASS DATE</span>
          <input
            type="date"
            className="search-input token-date-input"
            value={classDate}
            max={today}
            onChange={(e) => setClassDate(e.target.value)}
            required
          />
        </label>
      </div>

      <div className="token-form-row">
        <label className="token-label">
          <span className="eyebrow">REASON</span>
          <textarea
            className="token-textarea"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Briefly describe why your attendance was not recorded despite attending class…"
            maxLength={500}
            rows={4}
            required
          />
          <span className="token-char-count">
            {reason.length}/500
          </span>
        </label>
      </div>

      {error && (
        <div className="token-error" role="alert">
          {error}
        </div>
      )}

      <button
        type="submit"
        className="token-submit"
        disabled={busy || !reason.trim()}
      >
        {busy ? "Submitting…" : "Submit Request"}
      </button>
    </form>
  );
}

/**
 * Teacher notifications page — shows all attendance tokens raised by students.
 * Marks unread tokens as read on mount via a useEffect.
 */
function NotificationsPage({ notifications, unreadCount, token, onMarkRead, onReview, formatDate }) {
  // Track per-token busy state: { [token_id]: "approve"|"reject"|null }
  const [busyMap, setBusyMap] = useState({});
  // Track per-token inline error: { [token_id]: string }
  const [errorMap, setErrorMap] = useState({});

  useEffect(() => {
    const unreadIds = notifications
      .filter((n) => !n.read_at)
      .map((n) => n.token_id);

    if (unreadIds.length === 0) return;

    fetch(`${API}/api/notifications/mark-read`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ token_ids: unreadIds }),
    })
      .then((r) => r.ok && onMarkRead(unreadIds))
      .catch(() => {});
  // Run once on mount — intentionally omit deps to avoid re-firing on re-render
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleReview(tokenId, action) {
    setBusyMap((prev) => ({ ...prev, [tokenId]: action }));
    setErrorMap((prev) => ({ ...prev, [tokenId]: null }));

    try {
      const resp = await fetch(
        `${API}/api/attendance-token/${tokenId}/review`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ action }),
        }
      );
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(data.detail || "Action failed.");
      }
      // Notify parent to update notifications state
      onReview(tokenId, data.status);
    } catch (err) {
      setErrorMap((prev) => ({
        ...prev,
        [tokenId]: err.message || "Something went wrong.",
      }));
    } finally {
      setBusyMap((prev) => ({ ...prev, [tokenId]: null }));
    }
  }

  return (
    <div key="notifications" className="page-enter">
      <Reveal as="section" className="panel notif-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">STUDENT REQUESTS</p>
            <h3>Attendance Tokens</h3>
          </div>
          <span className="record-count">
            {notifications.length} total
            {unreadCount > 0 && (
              <span className="notif-unread-chip">{unreadCount} new</span>
            )}
          </span>
        </div>

        {notifications.length === 0 ? (
          <div className="activity-empty">
            <div className="empty-mark">◉</div>
            <h3>No tokens yet</h3>
            <p>
              When a student raises an attendance token it will appear here.
            </p>
          </div>
        ) : (
          <div className="notif-list">
            {notifications.map((n) => {
              const isBusy = !!busyMap[n.token_id];
              const itemError = errorMap[n.token_id];
              return (
                <div
                  key={n.token_id}
                  className={`notif-item${n.read_at ? "" : " notif-item--unread"}`}
                >
                  <div className="notif-item-header">
                    <span className="notif-token-id">
                      {!n.read_at && (
                        <span className="notif-dot" aria-label="Unread" />
                      )}
                      {n.token_id}
                    </span>
                    <span
                      className={`notif-status-badge notif-status--${n.status.toLowerCase()}`}
                    >
                      {n.status}
                    </span>
                  </div>

                  <div className="notif-item-body">
                    <div className="notif-field">
                      <span className="eyebrow">STUDENT</span>
                      <span>{n.student_name}</span>
                      <span className="notif-sub">{n.student_id}</span>
                    </div>
                    <div className="notif-field">
                      <span className="eyebrow">CLASS DATE</span>
                      <span>{formatDate(n.class_date)}</span>
                    </div>
                    <div className="notif-field">
                      <span className="eyebrow">SUBMITTED</span>
                      <span>{n.submitted_at} UTC</span>
                    </div>
                  </div>

                  <div className="notif-reason">
                    <span className="eyebrow">REASON</span>
                    <p>{n.reason}</p>
                  </div>

                  {n.status === "Pending" && (
                    <div className="notif-actions">
                      <button
                        className="notif-action-btn notif-action-btn--approve"
                        disabled={isBusy}
                        onClick={() => handleReview(n.token_id, "approve")}
                      >
                        {busyMap[n.token_id] === "approve"
                          ? "Approving…"
                          : "Approve"}
                      </button>
                      <button
                        className="notif-action-btn notif-action-btn--reject"
                        disabled={isBusy}
                        onClick={() => handleReview(n.token_id, "reject")}
                      >
                        {busyMap[n.token_id] === "reject"
                          ? "Rejecting…"
                          : "Reject"}
                      </button>
                    </div>
                  )}

                  {itemError && (
                    <p className="notif-action-error" role="alert">
                      {itemError}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Reveal>
    </div>
  );
}

function App() {
  const [token, setToken] = useState(
    () => sessionStorage.getItem("sa_token") || ""
  );

  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(
        sessionStorage.getItem("sa_user") || "null"
      );
    } catch {
      return null;
    }
  });

  const [activePage, setActivePage] = useState("Overview");
  const [search, setSearch] = useState("");
  const [stats, setStats] = useState(null);
  const [students, setStudents] = useState([]);
  const [attendance, setAttendance] = useState([]);
  const [myData, setMyData] = useState(null);
  const [pctData, setPctData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showPreviousDay, setShowPreviousDay] = useState(false);
  const [attendanceDateOffset, setAttendanceDateOffset] = useState(0);
  const [notifications, setNotifications] = useState([]);
  const [toast, setToast] = useState(null);
  // Refs to track previous counts for change detection
  const prevPresentTodayRef = useRef(null);
  const prevStudentAttendanceRef = useRef(null);

  function handleLogin(newToken, newUser) {
    sessionStorage.setItem("sa_token", newToken);
    sessionStorage.setItem(
      "sa_user",
      JSON.stringify(newUser)
    );

    setToken(newToken);
    setUser(newUser);
    setActivePage(
      newUser.role === "teacher"
        ? "Overview"
        : "My Attendance"
    );
    setLoading(true);
  }

  async function logout() {
    try {
      await fetch(`${API}/api/logout`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
    } catch {
      // Clear the local login even if the API is unreachable.
    }

    sessionStorage.removeItem("sa_token");
    sessionStorage.removeItem("sa_user");

    setToken("");
    setUser(null);
    setStats(null);
    setStudents([]);
    setAttendance([]);
    setMyData(null);
    setPctData(null);
    setError("");
    setSearch("");
    setNotifications([]);
    setLoading(false);
  }

  async function loadData() {
    if (!token || !user) return;

    try {
      if (user.role === "teacher") {
        const [
          statsData,
          studentsData,
          attendanceData,
        ] = await Promise.all([
          apiFetch("/api/stats", token),
          apiFetch("/api/students", token),
          apiFetch("/api/attendance", token),
        ]);

        setStats(statsData);
        setStudents(studentsData);
        setAttendance(attendanceData);

        // Fetch notifications (attendance tokens raised by students)
        try {
          const notifData = await apiFetch("/api/notifications", token);
          setNotifications(notifData);
        } catch {
          // Non-fatal: notifications panel just shows stale data
        }

        // Detect new attendance recorded since last refresh (teacher view)
        const newPresent = attendanceData.filter(
          (r) => r.date === statsData.date
        ).length;
        if (
          prevPresentTodayRef.current !== null &&
          newPresent > prevPresentTodayRef.current
        ) {
          const diff = newPresent - prevPresentTodayRef.current;
          setToast(
            `${diff} new attendance record${diff > 1 ? "s" : ""} added`
          );
        }
        prevPresentTodayRef.current = newPresent;
      } else {
        const [data, pct] = await Promise.all([
          apiFetch("/api/my-attendance", token),
          apiFetch("/api/my-attendance/percentage", token),
        ]);

        setMyData(data);
        setAttendance(data.attendance || []);
        setPctData(pct);

        // Detect when student's own attendance is newly recorded
        const newCount = (data.attendance || []).length;
        if (
          prevStudentAttendanceRef.current !== null &&
          newCount > prevStudentAttendanceRef.current
        ) {
          setToast("Your attendance has been recorded");
        }
        prevStudentAttendanceRef.current = newCount;
      }

      setError("");
    } catch (err) {
      setError(
        err.message || "Cannot connect to the backend."
      );

      if (
        /session expired|please log in/i.test(
          err.message || ""
        )
      ) {
        sessionStorage.removeItem("sa_token");
        sessionStorage.removeItem("sa_user");
        setToken("");
        setUser(null);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!token || !user) {
      setLoading(false);
      return;
    }

    loadData();

    const interval = setInterval(loadData, 10000);

    return () => clearInterval(interval);
  }, [token, user?.role, user?.student_id]);

  if (!token || !user) {
    return <LoginPage onLogin={handleLogin} />;
  }

  const isTeacher = user.role === "teacher";

  const today =
    stats?.date ||
    myData?.date ||
    (() => {
      const now = new Date();

      return `${now.getFullYear()}-${String(
        now.getMonth() + 1
      ).padStart(2, "0")}-${String(
        now.getDate()
      ).padStart(2, "0")}`;
    })();

  const selectedDate = (() => {
    const base = new Date(`${today}T00:00:00`);

    if (showPreviousDay) {
      base.setDate(base.getDate() - 1);
    }

    return `${base.getFullYear()}-${String(
      base.getMonth() + 1
    ).padStart(2, "0")}-${String(
      base.getDate()
    ).padStart(2, "0")}`;
  })();

  const selectedSchedule =
    WEEKLY_SCHEDULE[
      new Date(`${selectedDate}T00:00:00`).getDay()
    ];

  const selectedDayAttendance = attendance
    .filter((record) => record.date === selectedDate)
    .sort((a, b) =>
      (a.time || "").localeCompare(b.time || "")
    );

  // Attendance page: independent date navigation (offset from today).
  const attendanceDate = (() => {
    const base = new Date(`${today}T00:00:00`);
    base.setDate(base.getDate() + attendanceDateOffset);
    return `${base.getFullYear()}-${String(
      base.getMonth() + 1
    ).padStart(2, "0")}-${String(
      base.getDate()
    ).padStart(2, "0")}`;
  })();

  const isAttendanceDateToday = attendanceDateOffset === 0;

  const attendanceDayRecords = attendance
    .filter((record) => record.date === attendanceDate)
    .filter((record) =>
      `${record.name} ${record.student_id}`
        .toLowerCase()
        .includes(search.toLowerCase())
    )
    .sort((a, b) => (a.time || "").localeCompare(b.time || ""));

  const filteredAttendance = attendance.filter((record) =>
    `${record.name} ${record.student_id} ${record.date}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  const presentToday = attendance.filter(
    (record) => record.date === today
  ).length;

  const attendanceRate = stats?.total_students
    ? Math.round(
        (presentToday / stats.total_students) * 1000
      ) / 10
    : 0;

  function exportCSV() {
    const headers = [
      "Student ID",
      "Name",
      "Date",
      "Time",
    ];

    const rows = filteredAttendance.map((record) => [
      record.student_id,
      record.name,
      record.date,
      record.time,
    ]);

    const escapeCSV = (value) =>
      `"${String(value ?? "").replace(/"/g, '""')}"`;

    const csv = [headers, ...rows]
      .map((row) => row.map(escapeCSV).join(","))
      .join("\r\n");

    const blob = new Blob(["\uFEFF" + csv], {
      type: "text/csv;charset=utf-8;",
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = "attendance-records.csv";
    link.click();

    URL.revokeObjectURL(url);
  }

  function exportDayCSV() {
    const headers = [
      "Student Name",
      "Student ID",
      "Date",
      "Time",
      "Status",
    ];

    const rows = selectedDayAttendance.map((record) => [
      record.name,
      record.student_id,
      record.date,
      record.time,
      "Present",
    ]);

    const escapeCSV = (value) =>
      `"${String(value ?? "").replace(/"/g, '""')}"`;

    const csv = [headers, ...rows]
      .map((row) => row.map(escapeCSV).join(","))
      .join("\r\n");

    const blob = new Blob(["\uFEFF" + csv], {
      type: "text/csv;charset=utf-8;",
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = `attendance-${selectedDate}.csv`;
    link.click();

    URL.revokeObjectURL(url);
  }

  function exportAttendanceDayCSV() {
    const headers = [
      "Student Name",
      "Student ID",
      "Date",
      "Time",
      "Status",
    ];

    // Export unfiltered records for the selected date (ignore search)
    const dayRecords = attendance
      .filter((record) => record.date === attendanceDate)
      .sort((a, b) => (a.time || "").localeCompare(b.time || ""));

    const rows = dayRecords.map((record) => [
      record.name,
      record.student_id,
      record.date,
      record.time,
      "Present",
    ]);

    const escapeCSV = (value) =>
      `"${String(value ?? "").replace(/"/g, '""')}"`;

    const csv = [headers, ...rows]
      .map((row) => row.map(escapeCSV).join(","))
      .join("\r\n");

    const blob = new Blob(["\uFEFF" + csv], {
      type: "text/csv;charset=utf-8;",
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = `attendance-${attendanceDate}.csv`;
    link.click();

    URL.revokeObjectURL(url);
  }

  const unreadCount = notifications.filter((n) => !n.read_at).length;

  const navigation = isTeacher
    ? [
        { label: "Overview", icon: "◫" },
        { label: "Attendance", icon: "▤" },
        { label: "Students", icon: "♙" },
        { label: "Notifications", icon: "◉", badge: unreadCount },
        { label: "System", icon: "⌘" },
      ]
    : [
        { label: "My Attendance", icon: "▤" },
      ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-text">
            <h2>Smart Attendance</h2>
            <p>FACE RECOGNITION SYSTEM</p>
          </div>
        </div>

        <div className="nav-caption">WORKSPACE</div>

        <nav>
          {navigation.map((item) => (
            <button
              key={item.label}
              className={`nav-item ${
                activePage === item.label ? "active" : ""
              }`}
              onClick={() => {
                setActivePage(item.label);
                setSearch("");
                if (item.label === "Attendance") {
                  setAttendanceDateOffset(0);
                }
              }}
            >
              <span className="nav-icon">
                {item.icon}
              </span>
              {item.label}
              {item.badge > 0 && (
                <span className="nav-badge">{item.badge}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <span
            className="online-dot"
            style={{
              background: error ? "#c75b51" : undefined,
            }}
          />

          <div>
            <strong>{user.name}</strong>

            <p>
              {isTeacher
                ? "Teacher account"
                : `Student · ${user.student_id}`}
            </p>

            <button
              className="text-button"
              onClick={logout}
            >
              Sign out
            </button>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span> {activePage}
          </div>

          <div className="system-status">
            <span
              className="online-dot"
              style={{
                background: error ? "#c75b51" : undefined,
              }}
            />

            {error ? "CONNECTION ISSUE" : "LOCAL MODE"}
          </div>
        </header>

        <section className="page-heading">
          <div>
            <p className="eyebrow">
              {isTeacher
                ? "TEACHER WORKSPACE / 01"
                : "STUDENT PORTAL / 01"}
            </p>

            <h1>{activePage}</h1>

            <p className="subtitle">
              {isTeacher
                ? "Manage class attendance and student records."
                : "View your own attendance status and history."}
            </p>
          </div>
        </section>

        {error && (
          <div
            className="panel connection-error"
            role="alert"
          >
            <strong>Connection issue</strong>
            <p>{error}</p>

            <button
              className="text-button"
              onClick={loadData}
            >
              Retry connection
            </button>
          </div>
        )}

        {isTeacher && activePage === "Overview" && (
          <div key="overview" className="page-enter">
            <div className="today-date">
              <span className="today-date-label">
                TODAY IS
              </span>

              <h2>
                {new Date().toLocaleDateString("en-IN", {
                  weekday: "long",
                })}
              </h2>

              <p>
                {new Date().toLocaleDateString("en-IN", {
                  day: "numeric",
                  month: "long",
                  year: "numeric",
                })}
              </p>
            </div>

            <section className="stats-grid">
              <Reveal as="article" className="stat-card" style={{ "--i": 0 }}>
                <p>Enrolled students</p>

                <h2>
                  <StatValue
                    value={stats?.total_students ?? null}
                    loading={loading}
                  />
                </h2>

                <span className="stat-note">
                  Students in the database
                </span>
              </Reveal>

              <Reveal as="article" className="stat-card highlighted" style={{ "--i": 1 }}>
                <p>Present today</p>

                <h2>
                  <StatValue
                    value={loading && stats == null ? null : presentToday}
                    loading={loading}
                  />
                </h2>

                <span className="stat-note">
                  Students recorded today
                </span>
              </Reveal>

              <Reveal as="article" className="stat-card" style={{ "--i": 2 }}>
                <p>Attendance rate</p>

                <h2>
                  {loading && stats == null ? (
                    <span className="stat-skeleton" />
                  ) : (
                    <><StatValue
                        value={loading && stats == null ? null : attendanceRate}
                        loading={loading}
                      />%</>
                  )}
                </h2>

                <span className="stat-note">
                  Of all enrolled students
                </span>
              </Reveal>
            </section>

            <BufferCountdown />

            <section className="workspace-grid overview-workspace">
              <article className="panel activity-panel">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">
                      LATEST RECORDS
                    </p>
                    <h3>Recent activity</h3>
                  </div>

                  <button
                    className="text-button"
                    onClick={() =>
                      setActivePage("Attendance")
                    }
                  >
                    View all ↗
                  </button>
                </div>

                <div className="class-summary">
                  <div className="class-summary-main">
                    <p className="eyebrow">
                      CLASS ATTENDANCE
                    </p>

                    <h3>{CLASS_TITLE}</h3>

                    <p className="class-time">
                      {selectedSchedule
                        ? selectedSchedule.label
                        : "Demo attendance — no class-time restriction"}

                      {selectedSchedule?.type === "lab"
                        ? " · Lab"
                        : ""}
                    </p>
                  </div>

                  <div className="class-date">
                    <span>
                      {showPreviousDay
                        ? "PREVIOUS DAY"
                        : "TODAY"}
                    </span>

                    <strong>
                      {formatDate(selectedDate)}
                    </strong>
                  </div>
                </div>

                <div className="attendance-day-toolbar">
                  <div>
                    <h4>Present students</h4>
                    <p>
                      {selectedDayAttendance.length} student(s)
                      recorded
                    </p>
                  </div>

                  <span className="record-count">
                    {selectedDayAttendance.length} PRESENT
                  </span>
                </div>

                {selectedDayAttendance.length === 0 ? (
                  <div className="activity-empty day-empty">
                    <div className="empty-mark">↳</div>

                    <h3>No attendance for this day</h3>

                    <p>
                      Records appear after a registered student
                      is recognized.
                    </p>
                  </div>
                ) : (
                  <div className="recent-list">
                    {selectedDayAttendance.map((record) => (
                      <div
                        className="verification-step attendance-person"
                        key={record.id}
                      >
                        <span className="online-dot" />

                        <span className="student-record-name">
                          {record.name}
                          <br />
                          <small>
                            Student ID: {record.student_id}
                          </small>
                        </span>

                        <span className="attendance-time">
                          <span className="present-badge">
                            Present
                          </span>
                          <small>{record.time}</small>
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                <div className="day-navigation">
                  <button
                    className="day-nav-button"
                    onClick={() => setShowPreviousDay(true)}
                    disabled={showPreviousDay}
                  >
                    ← Previous Day
                  </button>

                  <button
                    className="day-nav-button"
                    onClick={() => setShowPreviousDay(false)}
                    disabled={!showPreviousDay}
                  >
                    Today
                  </button>

                  <button
                    className="day-nav-button day-nav-button--download"
                    onClick={exportDayCSV}
                    disabled={selectedDayAttendance.length === 0}
                    title={
                      selectedDayAttendance.length === 0
                        ? "No records to download for this day"
                        : `Download attendance for ${selectedDate}`
                    }
                  >
                    Download ↓
                  </button>
                </div>

                <div className="activity-footer">
                  <span className="online-dot" />
                  Refreshes every 10 seconds
                </div>
              </article>
            </section>
          </div>
        )}

        {isTeacher && activePage === "Attendance" && (
          <div key="attendance" className="page-enter">
          <Reveal as="section" className="panel records-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">
                  RECORD MANAGEMENT
                </p>
                <h3>Attendance records</h3>
              </div>

              <button
                className="text-button"
                onClick={exportAttendanceDayCSV}
                disabled={attendanceDayRecords.length === 0 && attendance.filter(r => r.date === attendanceDate).length === 0}
                title={`Download attendance for ${attendanceDate}`}
              >
                Download Attendance ↓
              </button>
            </div>

            <div className="attendance-page-toolbar">
              <div className="attendance-page-nav">
                <button
                  className="day-nav-button"
                  onClick={() =>
                    setAttendanceDateOffset((o) => o - 1)
                  }
                >
                  ← Previous Day
                </button>

                <span className="attendance-page-date">
                  {formatDate(attendanceDate)}
                  {isAttendanceDateToday && (
                    <span className="attendance-today-badge">Today</span>
                  )}
                </span>

                <button
                  className="day-nav-button"
                  onClick={() =>
                    setAttendanceDateOffset((o) => o + 1)
                  }
                  disabled={isAttendanceDateToday}
                >
                  Next Day →
                </button>
              </div>

              <input
                className="search-input attendance-page-search"
                placeholder="Search by student name or ID..."
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value)
                }
              />
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>STUDENT NAME</th>
                    <th>STUDENT ID</th>
                    <th>DATE</th>
                    <th>TIME</th>
                    <th>STATUS</th>
                  </tr>
                </thead>

                <tbody>
                  {attendanceDayRecords.map((record) => (
                    <tr key={record.id}>
                      <td>{record.name}</td>
                      <td>{record.student_id}</td>
                      <td>{record.date}</td>
                      <td>{record.time}</td>
                      <td>
                        <span className="present-badge">
                          Present
                        </span>
                      </td>
                    </tr>
                  ))}

                  {!loading &&
                    attendanceDayRecords.length === 0 && (
                      <tr>
                        <td colSpan="5">
                          {search
                            ? "No matching records found."
                            : "No attendance records for this day."}
                        </td>
                      </tr>
                    )}
                </tbody>
              </table>
            </div>

            <p className="preview-notice">
              {attendance.filter(r => r.date === attendanceDate).length} record(s) for {attendanceDate}.
            </p>
          </Reveal>
          </div>
        )}

        {isTeacher && activePage === "Students" && (
          <div key="students" className="page-enter">
          <Reveal as="section" className="panel records-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">
                  STUDENT DIRECTORY
                </p>
                <h3>Enrolled students</h3>
              </div>

              <span className="record-count">
                {students.length} students
              </span>
            </div>

            <input
              className="search-input"
              placeholder="Search by student name or ID..."
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
            />

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>STUDENT ID</th>
                    <th>NAME</th>
                    <th>ENROLLMENT</th>
                  </tr>
                </thead>

                <tbody>
                  {students
                    .filter((student) =>
                      `${student.name} ${student.student_id}`
                        .toLowerCase()
                        .includes(search.toLowerCase())
                    )
                    .map((student) => (
                      <tr key={student.student_id}>
                        <td>{student.student_id}</td>
                        <td>{student.name}</td>
                        <td>
                          <span className="present-badge">
                            Enrolled
                          </span>
                        </td>
                      </tr>
                    ))}

                  {!loading && students.length === 0 && (
                    <tr>
                      <td colSpan="3">
                        No enrolled students found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Reveal>
          </div>
        )}

        {isTeacher && activePage === "Notifications" && (
          <NotificationsPage
            key="notifications"
            notifications={notifications}
            unreadCount={unreadCount}
            token={token}
            onMarkRead={(ids) => {
              const now = new Date().toISOString().replace("T", " ").slice(0, 19);
              setNotifications((prev) =>
                prev.map((n) =>
                  ids.includes(n.token_id) ? { ...n, read_at: now } : n
                )
              );
            }}
            onReview={(tokenId, newStatus) => {
              setNotifications((prev) =>
                prev.map((n) =>
                  n.token_id === tokenId ? { ...n, status: newStatus } : n
                )
              );
            }}
            formatDate={formatDate}
          />
        )}

        {isTeacher && activePage === "System" && (
          <div key="system" className="page-enter">
          <Reveal as="section" className="panel simple-panel">
            <p className="eyebrow">SYSTEM HEALTH</p>
            <h3>Recognition services</h3>

            <p>
              Backend: {error ? "Disconnected" : "Reachable"}
            </p>

            <p>
              Database:{" "}
              {error
                ? "Not verified"
                : "Connected through API"}
            </p>

            <p>
              Face recognition runs separately through the
              Python program.
            </p>

            <button
              className="text-button"
              onClick={loadData}
            >
              Refresh status ↻
            </button>
          </Reveal>
          </div>
        )}

        {!isTeacher && activePage === "My Attendance" && (
          <div key="my-attendance" className="page-enter">
            <section className="stats-grid stats-grid--four">
              <Reveal as="article" className="stat-card" style={{ "--i": 0 }}>
                <p>Student</p>

                <h2 style={{ fontSize: 22 }}>
                  {myData?.name || user.name}
                </h2>

                <span className="stat-note">
                  ID: {user.student_id}
                </span>
              </Reveal>

              <Reveal as="article" className="stat-card highlighted" style={{ "--i": 1 }}>
                <p>Today's status</p>

                <h2 style={{ fontSize: 22 }}>
                  {loading && myData == null ? (
                    <span className="stat-skeleton stat-skeleton--sm" />
                  ) : myData?.present_today ? (
                    "Present"
                  ) : (
                    "Not marked"
                  )}
                </h2>

                <span className="stat-note">
                  {myData?.present_today
                    ? "Your attendance is recorded today."
                    : "No attendance record found for today."}
                </span>
              </Reveal>

              <Reveal as="article" className="stat-card" style={{ "--i": 2 }}>
                <p>Total records</p>
                <h2>
                  <StatValue
                    value={loading && myData == null ? null : attendance.length}
                    loading={loading}
                  />
                </h2>

                <span className="stat-note">
                  Your recorded attendance
                </span>
              </Reveal>

              <Reveal
                as="article"
                className="stat-card"
                style={{
                  "--i": 3,
                  ...(!loading &&
                  pctData?.percentage !== null &&
                  pctData?.percentage !== undefined &&
                  pctData.percentage < 75
                    ? { borderColor: "#f5ccc8", background: "#fff8f7" }
                    : {}),
                }}
              >
                <p>Attendance</p>

                <h2
                  style={{
                    fontSize:
                      !loading && pctData?.sessions_held > 0
                        ? 26
                        : 20,
                    color:
                      !loading &&
                      pctData?.percentage !== null &&
                      pctData?.percentage !== undefined &&
                      pctData.percentage < 75
                        ? "#c75b51"
                        : undefined,
                  }}
                >
                  {loading && pctData == null ? (
                    <span className="stat-skeleton stat-skeleton--sm" />
                  ) : pctData === null || pctData.sessions_held === 0 ? (
                    "—"
                  ) : (
                    <>
                      <StatValue value={pctData.sessions_attended} loading={false} />
                      /
                      <StatValue value={pctData.sessions_held} loading={false} />
                    </>
                  )}
                </h2>

                <span
                  className="stat-note"
                  style={{
                    color:
                      !loading &&
                      pctData?.percentage !== null &&
                      pctData?.percentage !== undefined &&
                      pctData.percentage < 75
                        ? "#c75b51"
                        : undefined,
                  }}
                >
                  {loading && pctData == null
                    ? ""
                    : pctData === null
                      ? "Fetching…"
                      : pctData.percentage === null
                        ? "Attendance percentage will appear after the first eligible class."
                        : pctData.percentage >= 75
                          ? `${pctData.percentage}% — sessions (${pctData.sessions_attended}/${pctData.sessions_held})`
                          : `${pctData.percentage}% ⚠ Below 75%`}
                </span>

                {!loading &&
                  pctData?.percentage !== null &&
                  pctData?.percentage !== undefined &&
                  pctData.percentage < 75 && (
                    <p
                      style={{
                        margin: "8px 0 0",
                        fontSize: 10,
                        color: "#c75b51",
                        lineHeight: 1.5,
                      }}
                    >
                      Attend {pctData.classes_needed} more consecutive session(s) to reach 75%.
                    </p>
                  )}
              </Reveal>
            </section>

            <section className="panel records-panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">
                    PERSONAL RECORDS
                  </p>
                  <h3>My attendance history</h3>
                </div>

                <span className="record-count">
                  {attendance.length} records
                </span>
              </div>

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>DATE</th>
                      <th>TIME</th>
                      <th>STATUS</th>
                    </tr>
                  </thead>

                  <tbody>
                    {attendance.map((record) => (
                      <tr key={record.id}>
                        <td>{record.date}</td>
                        <td>{record.time}</td>
                        <td>
                          <span className="present-badge">
                            Present
                          </span>
                        </td>
                      </tr>
                    ))}

                    {!loading && attendance.length === 0 && (
                      <tr>
                        <td colSpan="3">
                          You do not have any attendance records yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <p className="preview-notice">
                Only attendance associated with your student ID is shown.
              </p>
            </section>

            <section className="panel token-panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">DISPUTE / CORRECTION</p>
                  <h3>Raise Attendance Token</h3>
                </div>
              </div>
              <p className="token-panel-desc">
                Were you present but not marked? Select the class date and
                describe what happened. This does not automatically update
                your attendance — your teacher will review the request.
              </p>
              <RaiseTokenForm
                token={token}
                onSuccess={(data) =>
                  setToast(`Token ${data.token_id} submitted for ${data.class_date}`)
                }
              />
            </section>
          </div>
        )}

        <footer className="page-footer">
          <span>SMART ATTENDANCE SYSTEM</span>
          <span>DESIGNED FOR CLARITY.</span>
        </footer>

        {toast && (
          <Toast
            message={toast}
            onDone={() => setToast(null)}
          />
        )}
      </main>
    </div>
  );
}


const styles = {
  loginShell: {
    minHeight: "100vh",
    display: "grid",
    placeItems: "center",
    padding: "32px 20px",
    background: "#f7f7f3",
    color: "#252922",
    fontFamily: '"DM Sans", sans-serif',
    position: "relative",
    overflow: "hidden",
    isolation: "isolate",
  },

  loginGlow: {
    position: "absolute",
    width: 480,
    height: 480,
    borderRadius: "50%",
    background: "rgba(101, 125, 96, 0.09)",
    filter: "blur(90px)",
    top: "-160px",
    right: "-100px",
    pointerEvents: "none",
    zIndex: -1,
  },

  loginCard: {
    position: "relative",
    width: "100%",
    maxWidth: 440,
    boxSizing: "border-box",
    padding: "38px 34px 28px",
    border: "1px solid #e6e7df",
    borderRadius: 22,
    background: "rgba(255, 255, 255, 0.94)",
    boxShadow: "0 18px 55px rgba(37, 41, 34, 0.07)",
    backdropFilter: "blur(16px)",
  },

  brandMark: {
    display: "grid",
    placeItems: "center",
    width: 50,
    height: 50,
    borderRadius: 15,
    background: "#4f6649",
    color: "#ffffff",
    fontFamily: "Manrope, sans-serif",
    fontSize: 17,
    fontWeight: 800,
    letterSpacing: "-1px",
    boxShadow: "0 5px 14px rgba(79, 102, 73, 0.18)",
  },

  kicker: {
    fontSize: 10,
    letterSpacing: 2,
    color: "#657d60",
    fontWeight: 800,
    marginTop: 25,
    marginBottom: 10,
    textTransform: "uppercase",
  },

  loginTitle: {
    fontFamily: "Manrope, sans-serif",
    fontSize: 34,
    letterSpacing: "-1.2px",
    lineHeight: 1.2,
    color: "#252922",
    margin: 0,
    fontWeight: 800,
  },

  loginSubtitle: {
    color: "#85877f",
    fontSize: 14,
    lineHeight: 1.7,
    marginTop: 10,
    marginBottom: 25,
  },

  roleSwitch: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    padding: 4,
    gap: 4,
    borderRadius: 12,
    background: "#f0f2ec",
    border: "1px solid #e6e7df",
    marginBottom: 22,
  },

  roleButton: {
    border: "1px solid transparent",
    background: "transparent",
    color: "#85877f",
    borderRadius: 9,
    padding: "11px 8px",
    cursor: "pointer",
    fontFamily: '"DM Sans", sans-serif',
    fontSize: 13,
    fontWeight: 600,
    transition: "all 160ms ease",
  },

  roleActive: {
    border: "1px solid #d8e2d2",
    background: "#ffffff",
    color: "#40563d",
    borderRadius: 9,
    padding: "11px 8px",
    cursor: "pointer",
    fontFamily: '"DM Sans", sans-serif',
    fontSize: 13,
    fontWeight: 700,
    boxShadow: "0 2px 7px rgba(37, 41, 34, 0.06)",
    transition: "all 160ms ease",
  },

  fieldLabel: {
    display: "grid",
    gap: 8,
    fontSize: 12,
    color: "#51554c",
    fontWeight: 700,
  },

  loginInput: {
    width: "100%",
    boxSizing: "border-box",
    padding: "13px 14px",
    borderRadius: 10,
    border: "1px solid #e0e3da",
    background: "#fafbf8",
    color: "#252922",
    outline: "none",
    fontFamily: '"DM Sans", sans-serif',
    fontSize: 14,
    transition: "border-color 160ms ease, box-shadow 160ms ease",
  },

  loginSubmit: {
    width: "100%",
    border: "1px solid #4f6649",
    borderRadius: 10,
    padding: 14,
    background: "#4f6649",
    color: "#ffffff",
    fontFamily: '"DM Sans", sans-serif',
    fontWeight: 700,
    fontSize: 14,
    cursor: "pointer",
    boxShadow: "0 5px 12px rgba(79, 102, 73, 0.14)",
    transition: "background 160ms ease, transform 160ms ease",
  },

  errorMessage: {
    borderRadius: 10,
    padding: 11,
    color: "#a63f38",
    background: "#fff1ef",
    border: "1px solid #f0d2ce",
    fontSize: 13,
    lineHeight: 1.5,
  },

  loginFoot: {
    color: "#85877f",
    textAlign: "center",
    fontSize: 12,
    lineHeight: 1.7,
    marginTop: 18,
  },

  copyright: {
    color: "#999c91",
    fontSize: 9,
    letterSpacing: 1.5,
    textAlign: "center",
    marginTop: 28,
    marginBottom: 0,
    fontWeight: 600,
  },
};

export default App;
