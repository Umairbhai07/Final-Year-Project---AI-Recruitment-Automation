"""Interview lockdown log and integrity rating.

The browser reports what happened (left full screen, switched tab, tried to paste, ...); the server stamps the
time, counts strikes and ends the interview once MAX_STRIKES is reached. Nothing here rejects a candidate on its
own: the recruiter sees the log and decides.
"""

from datetime import UTC, datetime

MAX_STRIKES = 3
MAX_STORED_EVENTS = 300
STRIKE_MERGE_SECONDS = 3  # leaving full screen also hides the tab and blurs the window: count it once

MAX_SNAPSHOTS = 30
# Leaving the interview window (or switching the camera off). Each one is a strike.
STRIKE_TYPES = {
    "fullscreen_exit",
    "tab_hidden",
    "window_blur",
    "page_reload",
    "multiple_tabs",
    "camera_off",
    "phone_detected",  # the browser only reports a phone after seeing it in several frames in a row
}
# Webcam observations: logged for the recruiter, never strikes (people look away to think).
WEBCAM_TYPES = {"no_face", "looking_away", "eyes_away"}

LABELS = {
    "fullscreen_exit": "Left full screen",
    "tab_hidden": "Switched to another tab or app",
    "window_blur": "Clicked outside the interview window",
    "page_reload": "Reloaded or reopened the interview page",
    "multiple_tabs": "Opened the interview in a second tab",
    "copy_attempt": "Tried to copy",
    "paste_attempt": "Tried to paste",
    "context_menu": "Tried to open the right-click menu",
    "devtools_key": "Tried to open developer tools",
    "blocked_key": "Pressed a blocked shortcut",
    "screenshot_key": "Pressed Print Screen",
    "second_screen": "A second screen was connected",
    "question_repeated": "Asked to hear the question again",
    "tts_unavailable": "Browser could not speak the question (text was shown)",
    "keyboard_lock_unavailable": "Browser could not lock system keys (Alt+Tab, Windows key)",
    "camera_off": "Camera was switched off or disconnected",
    "no_face": "Face not visible",
    "multiple_faces": "More than one face in the camera",
    "looking_away": "Turned head away from the screen",
    "eyes_away": "Eyes looking away from the screen",
    "attention": "Attention during the answer",
    "time_expired": "Time ran out before an answer was recorded",
    "late_answer": "Answer arrived later than the time limit allows",
    "terminated": "Interview ended automatically",
    "second_device": "Tried to open the interview on a second device",
    "device_reset": "Recruiter allowed a new device",
    "phone_detected": "Mobile phone seen on camera",
    "book_detected": "Book or notes seen on camera",
    "screen_detected": "Another screen or laptop seen on camera",
    "object_detection_unavailable": "Object detection could not run in this browser",
}
CLIENT_TYPES = set(LABELS) - {"late_answer", "terminated", "time_expired", "second_device", "device_reset"}
SNAPSHOT_REASONS = {
    "start",
    "random",
    "no_face",
    "multiple_faces",
    "looking_away",
    "eyes_away",
    "phone_detected",
    "book_detected",
    "screen_detected",
}
LABELS |= {"start": "Start of interview", "random": "Random check"}
# Worth a recruiter's attention, but not leaving the window.
WARNING_TYPES = {
    "copy_attempt",
    "paste_attempt",
    "devtools_key",
    "screenshot_key",
    "second_screen",
    "late_answer",
    "object_detection_unavailable",
}
HIGH_TYPES = {
    "devtools_key",
    "late_answer",
    "multiple_tabs",
    "multiple_faces",
    "second_device",
    "phone_detected",
    "book_detected",
    "screen_detected",
}
WEBCAM_WARNING_COUNT, WEBCAM_HIGH_COUNT = 3, 10  # no_face + looking_away + eyes_away episodes
ATTENTION_WARNING, ATTENTION_HIGH = 75, 50  # average % of answer time looking at the screen


def _now() -> datetime:
    return datetime.now(UTC)


def add_event(
    session, type_: str, question_index: int | None = None, detail: str | None = None, value: float | None = None
) -> bool:
    """Append one event (server time). Returns True when it counted as a new strike."""
    events = list(session.integrity_events or [])
    now = _now()
    is_strike = type_ in STRIKE_TYPES
    if is_strike:
        last = next((e for e in reversed(events) if e.get("strike")), None)
        if last and (now - datetime.fromisoformat(last["at"])).total_seconds() < STRIKE_MERGE_SECONDS:
            is_strike = False  # same exit reported by several browser events
    if len(events) < MAX_STORED_EVENTS or is_strike or type_ == "terminated":
        events.append(
            {
                "type": type_,
                "at": now.isoformat(),
                "question_index": question_index,
                "detail": (detail or "")[:200] or None,
                "value": value,
                "strike": is_strike,
            }
        )
    session.integrity_events = events  # new list so SQLAlchemy sees the change
    return is_strike


def strikes(session) -> int:
    return sum(1 for e in (session.integrity_events or []) if e.get("strike"))


def attention(session) -> dict | None:
    """Share of each answer the candidate spent looking at the screen (from the browser's face tracking)."""
    per_q: dict[int, float] = {}
    for e in session.integrity_events or []:
        if e["type"] == "attention" and e.get("value") is not None and e.get("question_index") is not None:
            per_q[e["question_index"]] = float(e["value"])  # last report for a question wins
    if not per_q:
        return None
    avg = round(sum(per_q.values()) / len(per_q), 1)
    return {"average": avg, "per_question": [{"question_index": q, "percent": v} for q, v in sorted(per_q.items())]}


def summary(session) -> dict:
    events = session.integrity_events or []
    counts: dict[str, int] = {}
    for e in events:
        if e["type"] == "attention":
            continue
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    n = strikes(session)
    webcam = sum(counts.get(t, 0) for t in WEBCAM_TYPES)
    att = attention(session)
    avg = att["average"] if att else 100
    if (
        session.terminated
        or n >= 2
        or any(t in counts for t in HIGH_TYPES)
        or webcam >= WEBCAM_HIGH_COUNT
        or avg < ATTENTION_HIGH
    ):
        level = "high"
    elif n == 1 or any(t in counts for t in WARNING_TYPES) or webcam >= WEBCAM_WARNING_COUNT or avg < ATTENTION_WARNING:
        level = "warning"
    else:
        level = "clean"
    snaps = session.snapshots or []
    return {
        "level": level,
        "strikes": n,
        "max_strikes": MAX_STRIKES,
        "terminated": bool(session.terminated),
        "terminated_reason": session.terminated_reason,
        "counts": [{"type": t, "label": LABELS.get(t, t), "count": c} for t, c in counts.items()],
        "events": [{**e, "label": LABELS.get(e["type"], e["type"])} for e in events if e["type"] != "attention"][-150:],
        "attention": att,
        "webcam_used": bool(snaps) or att is not None,
        "snapshots": [
            {k: s[k] for k in ("index", "at", "reason", "question_index")}
            | {"label": LABELS.get(s["reason"], s["reason"])}
            for s in snaps
        ],
    }
