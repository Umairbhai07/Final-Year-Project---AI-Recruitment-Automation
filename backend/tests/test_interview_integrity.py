"""Strict interview: live follow-up questions, timing, lockdown strikes and the recruiter's integrity report."""

import uuid
from datetime import UTC, datetime, timedelta

from app.models import Application
from app.services import integrity
from app.services.interview import _follow_up_targets
from tests.conftest import JOB_PAYLOAD, STRONG_RESUME, apply, make_pdf
from tests.test_interview import GOOD_AUDIO, SILENT_AUDIO, _answer


def _job(client, recruiter, **extra):
    r = client.post("/api/jobs", json={**JOB_PAYLOAD, **extra}, headers=recruiter)
    assert r.status_code == 201, r.text
    return r.json()


def _started(client, candidate, job, db):
    app_id = apply(client, candidate, job["id"], make_pdf(STRONG_RESUME)).json()["id"]
    a = db.get(Application, uuid.UUID(app_id))
    sid = str(a.interview.id)
    state = client.post(f"/api/interviews/{sid}/start", headers=candidate).json()
    return a, sid, state


def _events(client, headers, sid, *types, q=0):
    return client.post(
        f"/api/interviews/{sid}/events",
        json={"events": [{"type": t, "question_index": q} for t in types]},
        headers=headers,
    )


def test_follow_up_targets_are_spread_and_never_last():
    assert _follow_up_targets(6, 1) == [2]
    assert _follow_up_targets(6, 2) == [1, 3]
    assert _follow_up_targets(5, 3) == [1, 2, 3]
    assert _follow_up_targets(5, 0) == []
    assert all(t < 5 for t in _follow_up_targets(5, 3))


def test_job_settings_validated(client, recruiter):
    job = _job(client, recruiter, think_seconds=20, follow_up_questions=2)
    assert job["think_seconds"] == 20 and job["follow_up_questions"] == 2
    assert client.post("/api/jobs", json={**JOB_PAYLOAD, "think_seconds": 2}, headers=recruiter).status_code == 422
    assert (
        client.post("/api/jobs", json={**JOB_PAYLOAD, "follow_up_questions": 4}, headers=recruiter).status_code == 422
    )


def test_live_follow_up_is_inserted_after_a_real_answer(client, recruiter, candidate, db):
    job = _job(client, recruiter, follow_up_questions=1)  # 5 main questions -> follow-up after main question 2
    a, sid, state = _started(client, candidate, job, db)
    assert state["total_questions"] == 5 and state["current_kind"] == "main"
    assert state["think_seconds"] == 15 and state["seconds_left"] > 120 + 15

    r = _answer(client, candidate, sid, 0, audio=GOOD_AUDIO + b"a").json()
    assert r["total_questions"] == 5 and r["next_kind"] == "main"
    r = _answer(client, candidate, sid, 1, audio=GOOD_AUDIO + b"b").json()
    assert r["total_questions"] == 6 and r["next_kind"] == "follow_up"
    assert r["next_question"].startswith("You said:")  # built from what the candidate just said

    for i in range(2, 6):
        r = _answer(client, candidate, sid, i, audio=GOOD_AUDIO + bytes([i])).json()
    assert r["completed"] is True

    detail = client.get(f"/api/applications/{a.id}/detail", headers=recruiter).json()
    kinds = [x["kind"] for x in detail["interview"]["responses"]]
    assert kinds == ["main", "main", "follow_up", "main", "main", "main"]
    assert detail["interview"]["questions"][2]["parent_index"] == 1
    assert detail["interview"]["integrity"]["level"] == "clean"


def test_no_follow_up_after_a_silent_answer(client, recruiter, candidate, db):
    job = _job(client, recruiter, follow_up_questions=1)
    a, sid, _ = _started(client, candidate, job, db)
    _answer(client, candidate, sid, 0, audio=GOOD_AUDIO + b"a")
    r = _answer(client, candidate, sid, 1, audio=SILENT_AUDIO).json()
    assert r["next_kind"] == "main" and r["total_questions"] == 5
    # still due, so the next real answer gets it
    r = _answer(client, candidate, sid, 2, audio=GOOD_AUDIO + b"c").json()
    assert r["next_kind"] == "follow_up" and r["total_questions"] == 6


def test_three_strikes_end_the_interview(client, recruiter, candidate, job, db, emails):
    a, sid, _ = _started(client, candidate, job, db)
    _answer(client, candidate, sid, 0)

    # leaving full screen also hides the tab and blurs the window: one strike, not three
    r = _events(client, candidate, sid, "fullscreen_exit", "tab_hidden", "window_blur", q=1).json()
    assert r == {"strikes": 1, "max_strikes": 3, "terminated": False}
    # paste attempts are logged but are not strikes
    assert _events(client, candidate, sid, "paste_attempt", q=1).json()["strikes"] == 1

    db.expire_all()
    session = db.get(Application, a.id).interview
    first = session.integrity_events[0]
    # pretend the next exits happen later so they are not merged
    events = [
        {**e, "at": (datetime.fromisoformat(e["at"]) - timedelta(minutes=5)).isoformat()}
        for e in session.integrity_events
    ]
    session.integrity_events = events
    db.commit()
    assert first["type"] == "fullscreen_exit" and first["strike"] is True

    r = _events(client, candidate, sid, "tab_hidden", q=1).json()
    assert r["strikes"] == 2 and not r["terminated"]
    db.expire_all()
    s = db.get(Application, a.id).interview
    s.integrity_events = [
        {**e, "at": (datetime.fromisoformat(e["at"]) - timedelta(minutes=1)).isoformat()} for e in s.integrity_events
    ]
    db.commit()
    r = _events(client, candidate, sid, "page_reload", q=1).json()
    assert r == {"strikes": 3, "max_strikes": 3, "terminated": True}

    db.expire_all()
    a = db.get(Application, a.id)
    assert a.stage == "evaluated" and a.interview.status == "completed" and a.interview.terminated
    # 1 answered + 4 unanswered (0 each)
    answered = a.interview.responses[0].score
    assert a.evaluation.interview_score == round(answered / 5 / 10 * 30, 1)
    assert _answer(client, candidate, sid, 1).status_code == 409
    state = client.get(f"/api/interviews/{sid}", headers=candidate).json()
    assert state["terminated"] is True and state["can_answer"] is False

    detail = client.get(f"/api/applications/{a.id}/detail", headers=recruiter).json()
    report = detail["interview"]["integrity"]
    assert report["level"] == "high" and report["terminated"] and report["strikes"] == 3
    labels = {c["label"] for c in report["counts"]}
    assert "Tried to paste" in labels and "Interview ended automatically" in labels
    rows = client.get(f"/api/jobs/{job['id']}/candidates", headers=recruiter).json()
    assert rows[0]["integrity_level"] == "high"
    csv = client.get(f"/api/jobs/{job['id']}/export", params={"format": "csv"}, headers=recruiter)
    assert csv.status_code == 200 and "Suspicious" in csv.text


def test_events_validation_and_ownership(client, recruiter, candidate, candidate2, job, db):
    a, sid, _ = _started(client, candidate, job, db)
    assert _events(client, candidate, sid, "terminated").status_code == 422  # server-only type
    assert _events(client, candidate, sid, "made_up").status_code == 422
    assert _events(client, candidate2, sid, "tab_hidden").status_code == 404
    assert _events(client, recruiter, sid, "tab_hidden").status_code == 403
    too_many = {"events": [{"type": "copy_attempt"}] * 21}
    assert client.post(f"/api/interviews/{sid}/events", json=too_many, headers=candidate).status_code == 422


def test_skip_when_time_runs_out_and_late_answers_flagged(client, recruiter, candidate, job, db):
    a, sid, _ = _started(client, candidate, job, db)
    assert client.post(f"/api/interviews/{sid}/skip", json={"question_index": 3}, headers=candidate).status_code == 409
    r = client.post(f"/api/interviews/{sid}/skip", json={"question_index": 0}, headers=candidate).json()
    assert r["next_index"] == 1 and r["seconds_left"] > 0

    # reopening the page does not reset the clock
    db.expire_all()
    s = db.get(Application, a.id).interview
    s.question_served_at = datetime.now(UTC) - timedelta(seconds=100)
    db.commit()
    left = client.get(f"/api/interviews/{sid}", headers=candidate).json()["seconds_left"]
    full = client.post(f"/api/interviews/{sid}/start", headers=candidate).json()["seconds_left"]
    assert left == full and 0 < left < 15 + 120 + 20 + 60 - 100 + 5

    # an answer that arrives far too late is accepted but flagged
    s = db.get(Application, a.id).interview
    s.question_served_at = datetime.now(UTC) - timedelta(minutes=30)
    db.commit()
    assert _answer(client, candidate, sid, 1).status_code == 200

    detail = client.get(f"/api/applications/{a.id}/detail", headers=recruiter).json()
    resp0 = detail["interview"]["responses"][0]
    assert resp0["score"] == 0 and "time ran out" in resp0["feedback"]
    types = [e["type"] for e in detail["interview"]["integrity"]["events"]]
    assert types == ["time_expired", "late_answer"]
    assert detail["interview"]["integrity"]["level"] == "high"


def test_summary_levels():
    class S:
        terminated = False
        terminated_reason = None
        integrity_events = []
        snapshots = []

    s = S()
    assert integrity.summary(s)["level"] == "clean"
    integrity.add_event(s, "question_repeated", 0)
    assert integrity.summary(s)["level"] == "clean"
    integrity.add_event(s, "copy_attempt", 0)
    assert integrity.summary(s)["level"] == "warning"
    integrity.add_event(s, "window_blur", 0)
    assert integrity.summary(s)["strikes"] == 1


JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 2000


def _snap(client, headers, sid, reason="start", data=JPEG, q=0):
    return client.post(
        f"/api/interviews/{sid}/snapshot",
        data={"reason": reason, "question_index": str(q)},
        files={"image": ("snap.jpg", data, "image/jpeg")},
        headers=headers,
    )


def test_webcam_snapshots_events_and_attention(client, recruiter, recruiter2, candidate, candidate2, job, db):
    a, sid, state = _started(client, candidate, job, db)
    assert state["require_webcam"] is True

    assert _snap(client, candidate, sid).json() == {"stored": True, "count": 1}
    assert _snap(client, candidate, sid, reason="looking_away", q=1).json()["count"] == 2
    assert _snap(client, candidate, sid, data=b"GIF89a" + b"\x00" * 100).status_code == 415
    assert _snap(client, candidate, sid, reason="selfie").status_code == 422
    assert _snap(client, candidate2, sid).status_code == 404

    # webcam observations are logged, never strikes
    r = _events(client, candidate, sid, "looking_away", "eyes_away", "no_face", q=0).json()
    assert r["strikes"] == 0
    for q, pct in ((0, 90), (1, 40)):
        ev = {"events": [{"type": "attention", "question_index": q, "value": pct}]}
        assert client.post(f"/api/interviews/{sid}/events", json=ev, headers=candidate).status_code == 200
    bad = {"events": [{"type": "attention", "question_index": 0, "value": 120}]}
    assert client.post(f"/api/interviews/{sid}/events", json=bad, headers=candidate).status_code == 422

    detail = client.get(f"/api/applications/{a.id}/detail", headers=recruiter).json()
    rep = detail["interview"]["integrity"]
    assert rep["attention"]["average"] == 65.0 and len(rep["attention"]["per_question"]) == 2
    assert rep["level"] == "warning"  # 3 webcam episodes and 65 % attention, no strikes
    assert [x["reason"] for x in rep["snapshots"]] == ["start", "looking_away"]
    assert "key" not in rep["snapshots"][0]  # storage paths are not exposed
    assert all(e["type"] != "attention" for e in rep["events"])

    img = client.get(f"/api/applications/{a.id}/snapshots/1", headers=recruiter)
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg" and img.content == JPEG
    assert client.get(f"/api/applications/{a.id}/snapshots/9", headers=recruiter).status_code == 404
    assert client.get(f"/api/applications/{a.id}/snapshots/0", headers=recruiter2).status_code == 404
    assert client.get(f"/api/applications/{a.id}/snapshots/0", headers=candidate).status_code == 403

    # two faces in the camera is treated as possible cheating
    _events(client, candidate, sid, "multiple_faces", q=1)
    assert (
        client.get(f"/api/applications/{a.id}/detail", headers=recruiter).json()["interview"]["integrity"]["level"]
        == "high"
    )

    # turning the camera off is a strike
    assert _events(client, candidate, sid, "camera_off", q=1).json()["strikes"] == 1


def test_recent_activity_sort_and_new_badges(client, recruiter, candidate, candidate2, job, db):
    a1, sid1, _ = _started(client, candidate, job, db)  # applied first
    r2 = apply(client, candidate2, job["id"], make_pdf(STRONG_RESUME)).json()  # applied second
    url = f"/api/jobs/{job['id']}/candidates"

    rows = client.get(url, headers=recruiter).json()  # default sort = latest activity
    assert [r["application_id"] for r in rows] == [r2["id"], str(a1.id)]
    assert all(r["is_new"] for r in rows)
    assert rows[1]["last_activity"] == "Started interview"

    # candidate 1 finishes the interview -> jumps to the top, marked New
    for i in range(5):
        _answer(client, candidate, sid1, i, audio=GOOD_AUDIO + bytes([i]))
    rows = client.get(url, headers=recruiter).json()
    assert rows[0]["application_id"] == str(a1.id) and rows[0]["last_activity"] == "Finished interview"
    assert rows[0]["interview_completed_at"]

    over = client.get("/api/dashboard/overview", headers=recruiter).json()
    assert over["recent_interviews"][0]["application_id"] == str(a1.id) and over["new_count"] == 2

    # opening the candidate clears New
    client.get(f"/api/applications/{a1.id}/detail", headers=recruiter)
    rows = client.get(url, headers=recruiter).json()
    assert {r["application_id"]: r["is_new"] for r in rows} == {str(a1.id): False, r2["id"]: True}
    assert client.get("/api/dashboard/overview", headers=recruiter).json()["new_count"] == 1
    assert client.get(url, params={"sort": "recent"}, headers=recruiter).status_code == 200


def test_attention_sent_with_the_answer(client, recruiter, candidate, job, db):
    """The browser sends the attention share together with the audio, so the last answer is never lost."""
    a, sid, _ = _started(client, candidate, job, db)
    post = lambda att: client.post(  # noqa: E731
        f"/api/interviews/{sid}/answer",
        data={"question_index": "0", "attention": att},
        files={"audio": ("answer.webm", GOOD_AUDIO, "audio/webm")},
        headers=candidate,
    )
    assert post("150").status_code == 422
    assert post("82.5").status_code == 200
    rep = client.get(f"/api/applications/{a.id}/detail", headers=recruiter).json()["interview"]["integrity"]
    assert rep["attention"] == {"average": 82.5, "per_question": [{"question_index": 0, "percent": 82.5}]}
    assert rep["webcam_used"] is True


def test_interview_is_locked_to_the_first_device(client, recruiter, candidate, job, db):
    a, sid, state = _started(client, candidate, job, db)
    assert state["device_locked"] and state["device_token"]
    token = state["device_token"]
    # the same browser can resume (and gets no new token)
    again = client.post(f"/api/interviews/{sid}/start", headers={**candidate, "X-Interview-Device": token}).json()
    assert again["device_token"] is None and again["current_index"] == 0
    # a second device (no token or a wrong one) is refused, and the attempt is logged for the recruiter
    other = {**candidate, "x-test-no-device": "1"}
    r = client.post(f"/api/interviews/{sid}/start", headers=other)
    assert r.status_code == 409 and "another device" in r.json()["detail"]
    r = client.post(f"/api/interviews/{sid}/start", headers={**candidate, "X-Interview-Device": "wrong-token"})
    assert r.status_code == 409
    assert _answer(client, other, sid, 0).status_code == 409
    assert client.post(f"/api/interviews/{sid}/skip", json={"question_index": 0}, headers=other).status_code == 409
    assert _events(client, other, sid, "tab_hidden").status_code == 409
    # the candidate can still report a problem from the other device
    assert (
        client.post(f"/api/interviews/{sid}/report-issue", json={"text": "Laptop died"}, headers=other).status_code
        == 204
    )
    detail = client.get(f"/api/applications/{a.id}/detail", headers=recruiter).json()
    assert detail["interview"]["device_locked"] is True
    labels = [e["label"] for e in detail["interview"]["integrity"]["events"]]
    assert "Tried to open the interview on a second device" in labels
    assert detail["interview"]["integrity"]["level"] == "high"
    assert detail["interview"]["integrity"]["strikes"] == 0  # logged, but not a warning against the candidate

    # the recruiter allows a new device; the next start locks to it
    r = client.post(f"/api/applications/{a.id}/interview/release-device", headers=recruiter)
    assert r.status_code == 200 and r.json()["interview"]["device_locked"] is False
    new = client.post(f"/api/interviews/{sid}/start", headers=other).json()
    assert new["device_token"] and new["device_token"] != token
    assert (
        client.post(f"/api/interviews/{sid}/start", headers={**candidate, "X-Interview-Device": token}).status_code
        == 409
    )


def test_phone_on_camera_is_a_strike_and_high_risk(client, recruiter, candidate, job, db):
    a, sid, _ = _started(client, candidate, job, db)
    r = _events(client, candidate, sid, "phone_detected").json()
    assert r["strikes"] == 1
    _events(client, candidate, sid, "book_detected")
    detail = client.get(f"/api/applications/{a.id}/detail", headers=recruiter).json()
    rep = detail["interview"]["integrity"]
    assert rep["level"] == "high" and rep["strikes"] == 1
    assert {c["label"] for c in rep["counts"]} >= {"Mobile phone seen on camera", "Book or notes seen on camera"}
    img = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    r = client.post(
        f"/api/interviews/{sid}/snapshot",
        files={"image": ("s.jpg", img, "image/jpeg")},
        data={"reason": "phone_detected", "question_index": "0"},
        headers=candidate,
    )
    assert r.status_code == 200 and r.json()["stored"]
