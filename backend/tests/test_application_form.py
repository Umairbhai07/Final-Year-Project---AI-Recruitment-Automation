import csv
import io
import uuid

from app.models import Application
from tests.conftest import JOB_PAYLOAD, STRONG_RESUME, WEAK_RESUME, apply, make_pdf

CUSTOM_FORM = [
    {
        "id": "total_experience",
        "label": "Total years of work experience",
        "type": "number",
        "required": True,
        "min": 0,
        "max": 50,
    },
    {
        "id": "highest_degree",
        "label": "Highest degree",
        "type": "select",
        "required": True,
        "options": ["Bachelor's", "Master's"],
    },
    {"id": "cgpa", "label": "Latest CGPA or grade", "type": "text", "required": False},
    {"id": "portfolio", "label": "GitHub or portfolio link", "type": "url", "required": False},
    {"id": "onsite", "label": "Can you work on-site in Lahore?", "type": "yes_no", "required": True},
]


def _job(client, recruiter, form):
    r = client.post("/api/jobs", json={**JOB_PAYLOAD, "application_form": form}, headers=recruiter)
    assert r.status_code == 201, r.text
    return r.json()


def test_new_job_starts_without_extra_questions(client, job):
    # degree, CGPA and experience come from the candidate's profile now
    assert job["application_form"] == []


def test_recruiter_defines_form_and_answers_are_validated(client, recruiter, candidate, db):
    job = _job(client, recruiter, CUSTOM_FORM)
    # candidates see the questions on the job page
    seen = client.get(f"/api/jobs/{job['id']}", headers=candidate).json()["application_form"]
    assert [q["id"] for q in seen] == [q["id"] for q in CUSTOM_FORM]

    pdf = make_pdf(STRONG_RESUME)
    good = {"total_experience": "3", "highest_degree": "Master's", "onsite": "Yes", "cgpa": "3.5"}
    cases = [
        ({**good, "total_experience": ""}, "Please answer: Total years of work experience"),
        ({**good, "total_experience": "abc"}, "must be a number"),
        ({**good, "total_experience": "80"}, "between 0 and 50"),
        ({**good, "highest_degree": "PhD"}, "Choose one of the options"),
        ({**good, "onsite": "maybe"}, "Yes or No"),
        ({**good, "portfolio": "github.com/me"}, "http"),
    ]
    for answers, message in cases:
        r = apply(client, candidate, job["id"], pdf, answers=answers)
        assert r.status_code == 422 and message in r.json()["detail"], (answers, r.text)
    bad_json = client.post(
        f"/api/jobs/{job['id']}/apply",
        files={"resume": ("r.pdf", pdf, "application/pdf")},
        data={"answers": "not json"},
        headers=candidate,
    )
    assert bad_json.status_code == 422

    r = apply(client, candidate, job["id"], pdf, answers={**good, "portfolio": "https://github.com/me", "x": "ignored"})
    assert r.status_code == 201, r.text
    app_ = db.get(Application, uuid.UUID(r.json()["id"]))
    assert [a["id"] for a in app_.form_answers] == ["total_experience", "highest_degree", "cgpa", "portfolio", "onsite"]
    assert app_.form_answers[0] == {"id": "total_experience", "label": "Total years of work experience", "answer": "3"}

    detail = client.get(f"/api/applications/{app_.id}/detail", headers=recruiter).json()
    assert {"id": "onsite", "label": "Can you work on-site in Lahore?", "answer": "Yes"} in detail["form_answers"]
    row = client.get(f"/api/jobs/{job['id']}/candidates", headers=recruiter).json()[0]
    assert any(a["id"] == "cgpa" and a["answer"] == "3.5" for a in row["form_answers"])

    csv_text = client.get(f"/api/jobs/{job['id']}/export", params={"format": "csv"}, headers=recruiter).content
    lines = list(csv.reader(io.StringIO(csv_text.decode("utf-8-sig"))))
    assert lines[1][-5:] == [q["label"] for q in CUSTOM_FORM]
    assert lines[2][-5:] == ["3", "Master's", "3.5", "https://github.com/me", "Yes"]


def test_form_definition_validation(client, recruiter, job):
    bad = [
        [{"id": "a", "label": "Pick", "type": "select", "options": ["only one"]}],
        [{"id": "a", "label": "One"}, {"id": "a", "label": "Two"}],
        [{"id": "Bad Id", "label": "x y"}],
        [{"id": f"q{i}", "label": f"Question {i}"} for i in range(16)],
    ]
    for form in bad:
        assert (
            client.post("/api/jobs", json={**JOB_PAYLOAD, "application_form": form}, headers=recruiter).status_code
            == 422
        )
    # no form at all is allowed, and editing the form works
    r = client.patch(f"/api/jobs/{job['id']}", json={"application_form": []}, headers=recruiter)
    assert r.status_code == 200 and r.json()["application_form"] == []


def test_profile_experience_fills_gaps_in_resume(client, recruiter, candidate, candidate2, db):
    """A resume without years of experience gets experience credit from the profile (mock AI)."""
    r = client.post("/api/jobs", json={**JOB_PAYLOAD, "min_experience_years": 0}, headers=recruiter)
    assert r.status_code == 201, r.text
    job = r.json()
    client.put("/api/profile/me", json={"experience_years": 0}, headers=candidate)
    client.put("/api/profile/me", json={"experience_years": 3}, headers=candidate2)
    resume = (
        "Ali Khan - Backend Developer\nSKILLS: Python, FastAPI, SQL, Git, Docker, REST APIs, unit testing\n"
        "PROJECTS: Built an online store API with FastAPI and PostgreSQL, deployed with Docker.\n"
        "EDUCATION: BS Computer Science, University of Lahore"
    )
    a1 = apply(
        client,
        candidate,
        job["id"],
        make_pdf(resume),
        answers={"total_experience": "0", "highest_degree": "Bachelor's", "cgpa": "3.0"},
    ).json()["id"]
    a2 = apply(
        client,
        candidate2,
        job["id"],
        make_pdf(resume),
        answers={"total_experience": "3", "highest_degree": "Bachelor's", "cgpa": "3.0"},
    ).json()["id"]
    e1 = db.get(Application, uuid.UUID(a1)).evaluation
    e2 = db.get(Application, uuid.UUID(a2)).evaluation
    assert e2.experience_score > e1.experience_score


def test_manual_invite_and_shortlist_visible_to_candidate(client, recruiter, recruiter2, candidate, job, db, emails):
    app_id = apply(
        client,
        candidate,
        job["id"],
        make_pdf(WEAK_RESUME),
        answers={"total_experience": "0", "highest_degree": "Bachelor's", "cgpa": "2.9"},
    ).json()["id"]
    assert db.get(Application, uuid.UUID(app_id)).stage == "not_qualified"
    mine = client.get("/api/applications/mine", headers=candidate).json()[0]
    assert mine["status_label"] == "Not selected" and not mine["can_start_interview"]

    assert client.post(f"/api/applications/{app_id}/invite", headers=recruiter2).status_code == 404
    assert client.post(f"/api/applications/{app_id}/invite", headers=candidate).status_code == 403
    r = client.post(f"/api/applications/{app_id}/invite", headers=recruiter)
    assert r.status_code == 200 and r.json()["stage"] == "interview_invited"
    assert (
        r.json()["interview"]["status"] == "invited" and len(r.json()["interview"]["questions"]) == job["num_questions"]
    )
    assert any("Interview invitation" in e["subject"] for e in emails)
    # a second invite is refused
    assert client.post(f"/api/applications/{app_id}/invite", headers=recruiter).status_code == 409

    mine = client.get("/api/applications/mine", headers=candidate).json()[0]
    assert mine["status_label"] == "Interview invited" and mine["can_start_interview"] is True

    client.patch(f"/api/applications/{app_id}/decision", json={"decision": "shortlisted"}, headers=recruiter)
    mine = client.get("/api/applications/mine", headers=candidate).json()[0]
    assert mine["status_label"] == "Shortlisted" and mine["shortlisted"] is True
    assert any("Good news" in e["subject"] for e in emails)
    client.patch(f"/api/applications/{app_id}/decision", json={"decision": "rejected"}, headers=recruiter)
    mine = client.get("/api/applications/mine", headers=candidate).json()[0]
    assert "reject" not in mine["status_label"].lower() and mine["shortlisted"] is False
