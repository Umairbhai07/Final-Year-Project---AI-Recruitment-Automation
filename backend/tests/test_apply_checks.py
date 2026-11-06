"""Hard checks after applying: someone else's resume, must-have answers, duplicate accounts, and the reason the
candidate sees straight away."""

import uuid

from app.config import settings
from app.models import AIAuditLog, Application
from tests.conftest import JOB_PAYLOAD, STRONG_RESUME, apply, make_pdf, register


def _app(db, application_id):
    a = db.get(Application, uuid.UUID(application_id))
    db.refresh(a)
    return a


def _mine(client, headers):
    return client.get("/api/applications/mine", headers=headers).json()[0]


def test_resume_with_someone_elses_name_is_not_selected(client, recruiter, db, monkeypatch):
    monkeypatch.setattr(settings, "CHECK_RESUME_NAME", True)
    job = client.post("/api/jobs", json=JOB_PAYLOAD, headers=recruiter).json()
    own = register(client, "ali@test.com", "candidate", name="Muhammad Ali Khan")  # resume says "Ali Khan"
    other = register(client, "sara@test.com", "candidate", name="Sara Ahmed")

    assert _app(db, apply(client, own, job["id"], make_pdf(STRONG_RESUME)).json()["id"]).stage == "interview_invited"

    a = _app(db, apply(client, other, job["id"], make_pdf(STRONG_RESUME)).json()["id"])
    assert a.stage == "not_qualified" and "someone else's resume" in a.review_reason
    assert not db.query(AIAuditLog).filter(AIAuditLog.application_id == a.id).count()  # stopped before the AI
    mine = _mine(client, other)
    assert mine["status_label"] == "Not selected" and "does not show your name (Sara Ahmed)" in mine["reason"]


def test_name_matching_rules():
    from app.services.profile import resume_has_name

    assert resume_has_name("Ali Hassan", "Muhammad Ali Hassan\nPython developer")
    assert resume_has_name("Muhammad Ali Hassan", "M. Ali Hassan - Backend")
    assert not resume_has_name("Ali Hassan", "Ali Khan\nPython developer")
    assert not resume_has_name("Muhammad Usman", "Muhammad Bilal, Lahore")
    assert resume_has_name("Ayesha", "AYESHA NOOR, Karachi")
    assert not resume_has_name("Hassan Raza", "Worked at Raza Traders")


def test_must_have_answers(client, recruiter, candidate, candidate2, db):
    form = [
        {"id": "onsite", "label": "Can you work on-site in Lahore?", "type": "yes_no", "accept": ["Yes"]},
        {"id": "expected_salary", "label": "Expected monthly salary (PKR)", "type": "number", "must_max": 150000},
    ]
    bad = {**JOB_PAYLOAD, "application_form": [{**form[0], "accept": ["Maybe"]}]}
    assert client.post("/api/jobs", json=bad, headers=recruiter).status_code == 422
    job = client.post("/api/jobs", json={**JOB_PAYLOAD, "application_form": form}, headers=recruiter).json()
    assert all(q["required"] for q in job["application_form"])  # a must-have question has to be answered

    # candidates see the questions but not which answer passes
    seen = client.get(f"/api/jobs/{job['id']}", headers=candidate).json()["application_form"]
    assert seen[0]["accept"] == [] and seen[1]["must_max"] is None

    r = apply(
        client, candidate, job["id"], make_pdf(STRONG_RESUME), answers={"onsite": "No", "expected_salary": "200000"}
    )
    a = _app(db, r.json()["id"])
    assert a.stage == "not_qualified"
    assert "Can you work on-site in Lahore?: needs Yes, you answered No" in a.review_reason
    assert "needs at most 150000, you answered 200000" in a.review_reason
    assert not db.query(AIAuditLog).filter(AIAuditLog.application_id == a.id).count()
    assert "must-have requirements" in _mine(client, candidate)["reason"]

    ok = {"onsite": "Yes", "expected_salary": "120000"}
    assert _app(db, apply(client, candidate2, job["id"], make_pdf(STRONG_RESUME), answers=ok).json()["id"]).stage == (
        "interview_invited"
    )


def test_duplicate_resume_and_phone_are_flagged(client, recruiter, candidate, candidate2, db):
    job = client.post("/api/jobs", json=JOB_PAYLOAD, headers=recruiter).json()
    pdf = make_pdf(STRONG_RESUME)
    first = _app(db, apply(client, candidate, job["id"], pdf).json()["id"])
    assert first.mismatches == ["The same phone number is on another account"]  # both test profiles share one
    second = _app(db, apply(client, candidate2, job["id"], pdf).json()["id"])
    assert "The same resume file was used by another account" in second.mismatches
    detail = client.get(f"/api/applications/{second.id}/detail", headers=recruiter).json()
    assert "The same resume file was used by another account" in detail["mismatches"]


def test_form_answers_are_compared_with_the_resume(client, recruiter, candidate, db):
    form = [{"id": "total_experience", "label": "Total years of work experience", "type": "number", "required": True}]
    job = client.post("/api/jobs", json={**JOB_PAYLOAD, "application_form": form}, headers=recruiter).json()
    a = _app(
        db, apply(client, candidate, job["id"], make_pdf(STRONG_RESUME), answers={"total_experience": "9"}).json()["id"]
    )
    assert any("Candidate says 9 years of experience" in m for m in a.mismatches)


def test_apply_answer_carries_the_result_on_serverless(client, recruiter, candidate, monkeypatch):
    monkeypatch.setattr(settings, "SERVERLESS", True)
    job = client.post("/api/jobs", json={**JOB_PAYLOAD, "min_experience_years": 6}, headers=recruiter).json()
    r = apply(client, candidate, job["id"], make_pdf(STRONG_RESUME)).json()
    assert r["stage"] == "not_qualified" and r["status_label"] == "Not selected"
    assert "Minimum experience needs 6 years or more" in r["reason"]
