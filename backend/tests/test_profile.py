"""Candidate profiles, strict minimum requirements, profile vs resume checks, and the recruiter's candidate view."""

import uuid

from app.config import settings
from app.models import Application
from tests.conftest import JOB_PAYLOAD, STRONG_RESUME, TINY_JPEG, apply, make_pdf, register

DIPLOMA_RESUME = STRONG_RESUME.replace(
    "Bachelor of Science in Computer Science (BSCS), Lahore Garrison University, 2021.",
    "Diploma of Associate Engineering (DAE) in Computer Information Technology, 2021.",
)


def test_new_candidate_must_complete_profile_before_applying(client, job):
    h = register(client, "new@test.com", "candidate", profile=False)
    me = client.get("/api/profile/me", headers=h).json()
    assert not me["complete"] and me["completion"] < 20 and "Photo" in me["missing"] and "Resume" in me["missing"]
    r = apply(client, h, job["id"], make_pdf(STRONG_RESUME))
    assert r.status_code == 409 and "Complete your profile" in r.json()["detail"]
    elig = client.get(f"/api/jobs/{job['id']}/eligibility", headers=h).json()
    assert elig["profile_complete"] is False and elig["eligible"] is False


def test_profile_validation(client, candidate):
    bad = [
        {"phone": "call me"},
        {"cgpa": 4.5},
        {"linkedin_url": "https://github.com/someone"},
        {"github_url": "https://example.com/x"},
        {"graduation_year": 2099},
    ]
    for body in bad:
        assert client.put("/api/profile/me", json=body, headers=candidate).status_code == 422, body
    r = client.put(
        "/api/profile/me",
        json={"github_url": "github.com/ali", "skills": ["Python", "python", " SQL "]},
        headers=candidate,
    )
    assert r.status_code == 200
    assert r.json()["github_url"] == "https://github.com/ali" and r.json()["skills"] == ["Python", "SQL"]
    # fields that were not sent stay as they were
    assert r.json()["city"] == "Lahore"


def test_profile_needs_only_basic_details(client):
    """Photo, phone, city and a resume. Degree, experience, CGPA and links are not asked for."""
    h = register(client, "basic@test.com", "candidate", profile=False)
    r = client.put("/api/profile/me", json={"phone": "+92 300 1234567", "city": "Karachi"}, headers=h).json()
    assert r["missing"] == ["Photo", "Resume"]
    client.post("/api/profile/me/photo", files={"image": ("me.jpg", TINY_JPEG, "image/jpeg")}, headers=h)
    pdf = make_pdf(STRONG_RESUME)
    r = client.post("/api/profile/me/resume", files={"resume": ("cv.pdf", pdf, "application/pdf")}, headers=h).json()
    assert r["complete"] and r["completion"] == 100
    me = client.get("/api/auth/me", headers=h).json()
    assert me["photo_url"].startswith("/api/photos/")  # shown in the account menu


def test_photo_upload_checks_type_and_signed_link(client, candidate):
    r = client.post(
        "/api/profile/me/photo", files={"image": ("x.jpg", b"not an image", "image/jpeg")}, headers=candidate
    )
    assert r.status_code == 415
    url = client.get("/api/profile/me", headers=candidate).json()["photo_url"]
    assert url.startswith("/api/photos/")
    assert client.get(url).status_code == 200 and client.get(url).content == TINY_JPEG  # no login header needed
    assert client.get(url.replace("sig=", "sig=0")).status_code == 404


def _stage(db, application_id):
    a = db.get(Application, uuid.UUID(application_id))
    db.refresh(a)
    return a


def test_minimum_requirements_are_checked_from_the_resume(client, recruiter, candidate, candidate2, db):
    job = client.post(
        "/api/jobs", json={**JOB_PAYLOAD, "min_experience_years": 4, "min_cgpa": 3.0}, headers=recruiter
    ).json()
    # before applying only the profile matters
    elig = client.get(f"/api/jobs/{job['id']}/eligibility", headers=candidate).json()
    assert elig == {"eligible": True, "profile_complete": True, "checks": []}

    # 3 years in the resume, the job needs 4: not qualified, with the reason, and counted as stopped
    r = apply(client, candidate, job["id"], make_pdf(STRONG_RESUME))
    assert r.status_code == 201
    a = _stage(db, r.json()["id"])
    assert a.stage == "not_qualified" and "Minimum experience needs 4 years or more" in a.review_reason
    assert client.get(f"/api/jobs/{job['id']}", headers=recruiter).json()["blocked_applications"] == 1
    detail = client.get(f"/api/applications/{a.id}/detail", headers=recruiter).json()
    by_rule = {c["rule"]: c for c in detail["requirements"]}
    assert not by_rule["experience"]["ok"] and by_rule["education"]["ok"]
    assert by_rule["cgpa"]["ok"] and by_rule["cgpa"]["yours"] == "Not shown in the resume"

    # a CGPA the resume states below the minimum
    job2 = client.post("/api/jobs", json={**JOB_PAYLOAD, "min_cgpa": 3.0}, headers=recruiter).json()
    low = STRONG_RESUME.replace("University, 2021.", "University, 2021. CGPA 2.6/4.0")
    a = _stage(db, apply(client, candidate2, job2["id"], make_pdf(low)).json()["id"])
    assert a.stage == "not_qualified" and "Minimum CGPA" in a.review_reason
    assert a.resume.parsed["cgpa"] == 2.6
    # a high enough CGPA passes
    ok = STRONG_RESUME.replace("University, 2021.", "University, 2021. CGPA 3.4")
    assert _stage(db, apply(client, candidate, job2["id"], make_pdf(ok)).json()["id"]).stage == "interview_invited"


def test_apply_with_profile_resume_and_snapshot(client, candidate, job, db):
    r = client.post(f"/api/jobs/{job['id']}/apply", data={"answers": "{}"}, headers=candidate)
    assert r.status_code == 201, r.text
    a = db.get(Application, uuid.UUID(r.json()["id"]))
    assert a.resume.original_filename == "cv.pdf" and a.stage == "interview_invited"
    assert a.profile_snapshot["city"] == "Lahore"
    assert a.mismatches == []


def test_resume_showing_lower_degree_is_not_qualified(client, candidate, job, db):
    """The job needs a Bachelor's and the resume shows a Diploma: not qualified, with the reason."""
    r = apply(client, candidate, job["id"], make_pdf(DIPLOMA_RESUME))
    a = db.get(Application, uuid.UUID(r.json()["id"]))
    assert a.stage == "not_qualified"
    assert "Minimum degree needs Bachelor's or higher, the resume shows Diploma" in a.review_reason


def test_recruiter_sees_profile_and_only_own_applications(client, recruiter, recruiter2, candidate, job):
    other = client.post("/api/jobs", json={**JOB_PAYLOAD, "title": "Other company job"}, headers=recruiter2).json()
    apply(client, candidate, job["id"], make_pdf(STRONG_RESUME))
    apply(client, candidate, other["id"], make_pdf(STRONG_RESUME))
    cand_id = client.get("/api/profile/me", headers=candidate).json()["user_id"]

    r = client.get(f"/api/candidates/{cand_id}", headers=recruiter)
    assert r.status_code == 200
    body = r.json()
    assert body["profile"]["city"] == "Lahore" and body["profile"]["photo_url"]
    assert [a["job_title"] for a in body["applications"]] == [job["title"]]
    assert client.get(f"/api/candidates/{cand_id}/resume", headers=recruiter).content.startswith(b"%PDF")

    # a recruiter the candidate never applied to cannot see them
    stranger = register(client, "rec3@test.com", "recruiter")
    assert client.get(f"/api/candidates/{cand_id}", headers=stranger).status_code == 404
    assert client.get(f"/api/candidates/{cand_id}", headers=candidate).status_code == 403


def test_email_is_unique_ignoring_case(client):
    register(client, "Same@Test.com", "candidate", profile=False)
    r = client.post(
        "/api/auth/register",
        json={"full_name": "Copy", "email": "same@test.COM", "password": "Passw0rd1", "role": "recruiter"},
    )
    assert r.status_code == 409 and "already exists" in r.json()["detail"]


def test_email_verification(client, emails, monkeypatch, job):
    h = register(client, "verify@test.com", "candidate")
    mail = next(m for m in emails if m["to"] == "verify@test.com" and m["subject"] == "Confirm your email")
    token = mail["html"].split("/verify-email?token=")[1].split("'")[0]
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    assert client.get("/api/auth/me", headers=h).json()["must_verify"] is True
    r = apply(client, h, job["id"], make_pdf(STRONG_RESUME))
    assert r.status_code == 403 and "confirm your email" in r.json()["detail"]
    assert client.post("/api/auth/verify-email", json={"token": "x" * 30}).status_code == 400
    r = client.post("/api/auth/verify-email", json={"token": token})
    assert r.status_code == 200 and r.json()["email_verified"] is True and r.json()["must_verify"] is False
    assert apply(client, h, job["id"], make_pdf(STRONG_RESUME)).status_code == 201
