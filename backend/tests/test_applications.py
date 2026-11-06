from datetime import date, timedelta

from sqlalchemy import select

from app.models import AIAuditLog, Application
from tests.conftest import JOB_PAYLOAD, STRONG_RESUME, WEAK_RESUME, apply, make_pdf


def test_recruiter_cannot_apply_403(client, recruiter, job):
    assert apply(client, recruiter, job["id"], make_pdf(STRONG_RESUME)).status_code == 403


def test_wrong_file_type_415(client, candidate, job):
    r = apply(client, candidate, job["id"], b"hello world", filename="resume.txt", ctype="text/plain")
    assert r.status_code == 415
    # PDF extension + MIME but not real PDF bytes
    r = apply(client, candidate, job["id"], b"not a pdf at all", filename="resume.pdf")
    assert r.status_code == 415
    # real PDF bytes but wrong extension
    r = apply(client, candidate, job["id"], make_pdf(STRONG_RESUME), filename="resume.docx")
    assert r.status_code == 415


def test_too_large_file_413(client, candidate, job):
    big = b"%PDF-1.4\n" + b"0" * (5 * 1024 * 1024 + 10)
    assert apply(client, candidate, job["id"], big).status_code == 413


def test_duplicate_application_409(client, candidate, job):
    assert apply(client, candidate, job["id"], make_pdf(STRONG_RESUME)).status_code == 201
    r = apply(client, candidate, job["id"], make_pdf(STRONG_RESUME))
    assert r.status_code == 409
    assert "already applied" in r.json()["detail"]


def test_cannot_apply_to_paused_or_past_deadline(client, recruiter, candidate, job):
    client.patch(f"/api/jobs/{job['id']}/status", json={"status": "paused"}, headers=recruiter)
    assert apply(client, candidate, job["id"], make_pdf(STRONG_RESUME)).status_code == 404
    payload = {**JOB_PAYLOAD, "deadline": (date.today() - timedelta(days=2)).isoformat()}
    old = client.post("/api/jobs", json=payload, headers=recruiter).json()
    assert apply(client, candidate, old["id"], make_pdf(STRONG_RESUME)).status_code == 400


def test_qualified_flow_invites_to_interview(client, candidate, job, db, emails):
    r = apply(client, candidate, job["id"], make_pdf(STRONG_RESUME))
    assert r.status_code == 201
    app_id = r.json()["id"]
    mine = client.get("/api/applications/mine", headers=candidate).json()
    assert len(mine) == 1
    assert mine[0]["status_label"] == "Interview invited"
    assert mine[0]["can_start_interview"] is True
    assert "score" not in str(mine[0]).lower()  # candidates never see scores

    a = db.get(Application, __import__("uuid").UUID(app_id))
    assert a.stage == "interview_invited"
    assert a.resume.parse_ok and a.resume.parsed["matched_skills"] == JOB_PAYLOAD["required_skills"]
    ev = a.evaluation
    assert ev.skill_score == 40 and ev.resume_total == ev.skill_score + ev.experience_score + ev.education_score
    assert ev.incomplete is True and ev.composite_score == ev.resume_total
    assert len(a.interview.questions) == JOB_PAYLOAD["num_questions"]
    subjects = [e["subject"] for e in emails]
    assert any("Application received" in s for s in subjects)
    assert any("Interview invitation" in s for s in subjects)
    kinds = {row.kind for row in db.scalars(select(AIAuditLog))}
    assert {"resume_screen", "question_gen"} <= kinds


def test_not_qualified_flow(client, candidate2, job, db, emails):
    r = apply(client, candidate2, job["id"], make_pdf(WEAK_RESUME))
    a = db.get(Application, __import__("uuid").UUID(r.json()["id"]))
    assert a.stage == "not_qualified"
    assert a.interview is None
    assert a.evaluation.resume_total < JOB_PAYLOAD["screening_threshold"]
    mine = client.get("/api/applications/mine", headers=candidate2).json()
    assert mine[0]["status_label"] == "Not selected"
    assert mine[0]["reason"] == "Your resume does not match this job's required skills and experience closely enough."
    assert not any("Interview invitation" in e["subject"] for e in emails)


def test_unreadable_pdf_needs_manual_review_and_rescreen(client, recruiter, candidate, job, db, emails):
    r = apply(client, candidate, job["id"], make_pdf(None))
    app_id = r.json()["id"]
    a = db.get(Application, __import__("uuid").UUID(app_id))
    assert a.stage == "screening_failed" and a.needs_manual_review
    assert "no readable text" in a.review_reason
    assert any("Manual review needed" in e["subject"] for e in emails)
    assert client.get("/api/applications/mine", headers=candidate).json()[0]["status_label"] == "Under review"
    # recruiter can re-run screening (it fails again for the same blank file, but the endpoint works)
    assert client.post(f"/api/applications/{app_id}/rescreen", headers=recruiter).status_code == 202
    db.expire_all()
    assert db.get(Application, a.id).stage == "screening_failed"


def test_rescreen_only_for_failed(client, recruiter, candidate, job):
    app_id = apply(client, candidate, job["id"], make_pdf(STRONG_RESUME)).json()["id"]
    assert client.post(f"/api/applications/{app_id}/rescreen", headers=recruiter).status_code == 409
    assert client.post(f"/api/applications/{app_id}/rescreen", headers=candidate).status_code == 403


def test_resume_download_ownership(client, recruiter, recruiter2, candidate, candidate2, job):
    app_id = apply(client, candidate, job["id"], make_pdf(STRONG_RESUME)).json()["id"]
    url = f"/api/applications/{app_id}/resume"
    for h in (recruiter, candidate):
        r = client.get(url, headers=h)
        assert r.status_code == 200 and r.content.startswith(b"%PDF")
        assert r.headers["content-type"] == "application/pdf"
    assert client.get(url, headers=recruiter2).status_code == 404
    assert client.get(url, headers=candidate2).status_code == 404
    assert client.get(url).status_code == 401


def test_has_applied_flag(client, candidate, job):
    assert client.get("/api/jobs", headers=candidate).json()[0]["has_applied"] is False
    apply(client, candidate, job["id"], make_pdf(STRONG_RESUME))
    assert client.get("/api/jobs", headers=candidate).json()[0]["has_applied"] is True


def test_closing_job_archives_applications(client, recruiter, candidate, job, db):
    app_id = apply(client, candidate, job["id"], make_pdf(STRONG_RESUME)).json()["id"]
    client.patch(f"/api/jobs/{job['id']}/status", json={"status": "closed"}, headers=recruiter)
    db.expire_all()
    assert db.get(Application, __import__("uuid").UUID(app_id)).archived is True
    assert client.get("/api/applications/mine", headers=candidate).json()[0]["can_start_interview"] is False
