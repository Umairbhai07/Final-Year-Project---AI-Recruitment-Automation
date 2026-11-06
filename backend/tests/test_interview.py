import uuid

from app.models import Application
from app.services import evaluation
from tests.conftest import STRONG_RESUME, apply, make_pdf

GOOD_AUDIO = b"\x1aE\xdf\xa3" + bytes(range(256)) * 40  # >2KB -> mock transcript with content
SILENT_AUDIO = b"\x1aE\xdf\xa3" + b"\x00" * 100  # tiny -> mock treats it as silence


def _invited(client, candidate, job, db):
    app_id = apply(client, candidate, job["id"], make_pdf(STRONG_RESUME)).json()["id"]
    a = db.get(Application, uuid.UUID(app_id))
    return a, str(a.interview.id)


def _answer(client, headers, sid, idx, audio=GOOD_AUDIO, name="answer.webm", ctype="audio/webm;codecs=opus"):
    return client.post(
        f"/api/interviews/{sid}/answer",
        data={"question_index": str(idx)},
        files={"audio": (name, audio, ctype)},
        headers=headers,
    )


def test_full_interview_flow_and_composite(client, recruiter, candidate, job, db, emails):
    a, sid = _invited(client, candidate, job, db)
    state = client.get(f"/api/interviews/{sid}", headers=candidate).json()
    assert state["status"] == "invited" and state["total_questions"] == 5 and state["current_index"] == 0
    assert state["seconds_per_question"] == 120 and state["can_answer"]

    # cannot answer before starting
    assert _answer(client, candidate, sid, 0).status_code == 409
    started = client.post(f"/api/interviews/{sid}/start", headers=candidate).json()
    assert started["status"] == "in_progress" and started["current_question"]

    # out-of-order answer rejected
    assert _answer(client, candidate, sid, 2).status_code == 409

    for i in range(5):
        audio = SILENT_AUDIO if i == 1 else GOOD_AUDIO + bytes([i])
        r = _answer(client, candidate, sid, i, audio=audio)
        assert r.status_code == 200, r.text
        assert r.json()["completed"] is (i == 4)
        if i < 4:
            assert r.json()["next_index"] == i + 1

    # each question answered once only
    assert _answer(client, candidate, sid, 4).status_code == 409

    db.expire_all()
    a = db.get(Application, a.id)
    assert a.stage == "evaluated" and a.interview.status == "completed"
    responses = sorted(a.interview.responses, key=lambda r: r.question_index)
    assert len(responses) == 5
    silent = responses[1]
    assert silent.score == 0 and silent.feedback == "No meaningful answer detected."
    for r in responses:
        assert r.score == evaluation.answer_score(r.accuracy, r.relevance, r.clarity)
    ev = a.evaluation
    expected_interview = round(sum(r.score for r in responses) / 5 / 10 * 30, 1)
    assert ev.interview_score == expected_interview
    assert ev.composite_score == round(ev.resume_total + expected_interview, 1)
    assert ev.incomplete is False
    subjects = [e["subject"] for e in emails]
    assert any("Interview completed" in s for s in subjects)
    assert any("New candidate evaluated" in s for s in subjects)

    # candidate sees completion state, no scores
    state = client.get(f"/api/interviews/{sid}", headers=candidate).json()
    assert state["status"] == "completed" and state["can_answer"] is False
    assert client.post(f"/api/interviews/{sid}/start", headers=candidate).status_code == 409
    mine = client.get("/api/applications/mine", headers=candidate).json()[0]
    assert mine["status_label"] == "Evaluated" and "score" not in str(mine).lower()

    # recruiter can play the recording
    r = client.get(f"/api/applications/{a.id}/audio/0", headers=recruiter)
    assert r.status_code == 200 and r.headers["content-type"].startswith("audio/webm")
    assert client.get(f"/api/applications/{a.id}/audio/0", headers=candidate).status_code == 403


def test_resume_after_reload_continues_from_current_index(client, candidate, job, db):
    _, sid = _invited(client, candidate, job, db)
    client.post(f"/api/interviews/{sid}/start", headers=candidate)
    _answer(client, candidate, sid, 0)
    _answer(client, candidate, sid, 1)
    state = client.get(f"/api/interviews/{sid}", headers=candidate).json()
    assert state["current_index"] == 2 and state["status"] == "in_progress"
    # calling start again is harmless
    assert client.post(f"/api/interviews/{sid}/start", headers=candidate).json()["current_index"] == 2


def test_interview_ownership_and_roles(client, recruiter, candidate, candidate2, job, db):
    _, sid = _invited(client, candidate, job, db)
    assert client.get(f"/api/interviews/{sid}", headers=candidate2).status_code == 404
    assert client.get(f"/api/interviews/{sid}", headers=recruiter).status_code == 403
    assert client.get(f"/api/interviews/{uuid.uuid4()}", headers=candidate).status_code == 404


def test_audio_validation(client, candidate, job, db):
    _, sid = _invited(client, candidate, job, db)
    client.post(f"/api/interviews/{sid}/start", headers=candidate)
    assert _answer(client, candidate, sid, 0, name="a.txt", ctype="text/plain").status_code == 415
    big = b"0" * (10 * 1024 * 1024 + 5)
    assert _answer(client, candidate, sid, 0, audio=big).status_code == 413
    assert _answer(client, candidate, sid, 0, audio=b"").status_code == 400
    assert _answer(client, candidate, sid, 0, name="a.mp3", ctype="audio/mpeg").status_code == 200


def test_report_issue(client, candidate, job, db):
    a, sid = _invited(client, candidate, job, db)
    assert (
        client.post(
            f"/api/interviews/{sid}/report-issue", json={"text": "Mic stopped working"}, headers=candidate
        ).status_code
        == 204
    )
    client.post(f"/api/interviews/{sid}/report-issue", json={"text": "Second problem"}, headers=candidate)
    db.expire_all()
    s = db.get(Application, a.id).interview
    assert s.issue_reported and "Mic stopped working" in s.issue_text and "Second problem" in s.issue_text


def test_closed_job_blocks_interview(client, recruiter, candidate, job, db):
    _, sid = _invited(client, candidate, job, db)
    client.patch(f"/api/jobs/{job['id']}/status", json={"status": "closed"}, headers=recruiter)
    assert client.post(f"/api/interviews/{sid}/start", headers=candidate).status_code == 409


def test_answer_is_kept_and_scored_later_when_ai_is_busy(client, recruiter, candidate, job, db, monkeypatch):
    """Under heavy load the AI may refuse requests. The candidate carries on; the answer is scored later."""
    from app.ai import client as ai

    a, sid = _invited(client, candidate, job, db)
    client.post(f"/api/interviews/{sid}/start", headers=candidate)
    real = ai.transcribe

    def busy(*args, **kwargs):
        raise ai.AIServiceError("RateLimitError: too many requests")

    monkeypatch.setattr(ai, "transcribe", busy)
    for i in range(5):
        r = _answer(client, candidate, sid, i, audio=GOOD_AUDIO + bytes([i]))
        assert r.status_code == 200, r.text
    db.expire_all()
    a = db.get(Application, a.id)
    assert a.stage == "evaluated" and all(r.pending for r in a.interview.responses)
    assert a.evaluation.incomplete is True

    monkeypatch.setattr(ai, "transcribe", real)  # the AI is free again
    detail = client.get(f"/api/applications/{a.id}/detail", headers=recruiter).json()
    assert not any(r["pending"] for r in detail["interview"]["responses"])
    assert detail["scores"]["incomplete"] is False and detail["scores"]["interview_score"] > 0
