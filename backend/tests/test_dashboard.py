import csv
import io
import uuid

from app.models import Application, EvaluationScore
from tests.conftest import STRONG_RESUME, WEAK_RESUME, apply, make_pdf, register
from tests.test_interview import GOOD_AUDIO, _answer

MEDIUM_RESUME = """Usman Tariq - Junior Developer
SKILLS: Python, Flask, SQL, HTML, CSS
EXPERIENCE: Intern at WebSoft for 1 year building small Flask apps and SQL reports.
EDUCATION: Bachelor of Science in Software Engineering, 2023. Final year project in Python."""


def _setup(client, recruiter, job, db):
    """Three candidates: strong (interview completed), medium (invited), weak (not qualified)."""
    heads = [
        register(client, f"c{i}@test.com", "candidate", name=n)
        for i, n in enumerate(["Strong One", "Medium Two", "Weak Three"])
    ]
    ids = []
    for h, text in zip(heads, [STRONG_RESUME, MEDIUM_RESUME, WEAK_RESUME], strict=False):
        ids.append(apply(client, h, job["id"], make_pdf(text)).json()["id"])
    strong = db.get(Application, uuid.UUID(ids[0]))
    sid = str(strong.interview.id)
    client.post(f"/api/interviews/{sid}/start", headers=heads[0])
    for i in range(5):
        assert _answer(client, heads[0], sid, i, audio=GOOD_AUDIO + bytes([i])).status_code == 200
    return heads, ids


def test_dashboard_ranking_and_filters(client, recruiter, recruiter2, candidate, job, db):
    heads, ids = _setup(client, recruiter, job, db)
    url = f"/api/jobs/{job['id']}/candidates"
    rows = client.get(url, params={"sort": "composite"}, headers=recruiter).json()
    assert len(rows) == 3
    scores = [r["composite_score"] for r in rows]
    assert scores == sorted(scores, reverse=True)
    assert [r["rank"] for r in rows] == [1, 2, 3]
    assert rows[0]["application_id"] == ids[0] and rows[0]["stage"] == "evaluated"
    assert rows[0]["interview_score"] is not None and rows[0]["incomplete"] is False

    assert {r["stage"] for r in client.get(url, params={"stage": "not_qualified"}, headers=recruiter).json()} == {
        "not_qualified"
    }
    high = client.get(url, params={"min_score": 50}, headers=recruiter).json()
    assert all(r["composite_score"] >= 50 for r in high)
    by_name = client.get(url, params={"sort": "name"}, headers=recruiter).json()
    assert [r["full_name"] for r in by_name] == sorted(r["full_name"] for r in rows)
    assert by_name[0]["rank"] != 0  # rank keeps composite position even when sorted by name
    assert client.get(url, params={"sort": "bogus"}, headers=recruiter).status_code == 422

    assert client.get(url, headers=recruiter2).status_code == 404
    assert client.get(url, headers=candidate).status_code == 403


def test_detail_decision_and_scores_read_only(client, recruiter, recruiter2, job, db):
    _, ids = _setup(client, recruiter, job, db)
    detail = client.get(f"/api/applications/{ids[0]}/detail", headers=recruiter).json()
    assert detail["candidate"]["full_name"] == "Strong One"
    assert detail["scores"]["composite_score"] > 0
    assert len(detail["interview"]["responses"]) == 5
    assert detail["interview"]["responses"][0]["transcript"]
    assert detail["parsed_resume"]["matched_skills"]
    assert client.get(f"/api/applications/{ids[0]}/detail", headers=recruiter2).status_code == 404

    before = db.get(EvaluationScore, uuid.UUID(detail["scores"] and _eval_id(db, ids[0])))
    payload = {"decision": "shortlisted", "notes": "Strong FastAPI answers", "composite_score": 100, "skill_score": 40}
    r = client.patch(f"/api/applications/{ids[0]}/decision", json=payload, headers=recruiter)
    assert r.status_code == 200
    assert r.json()["decision"] == "shortlisted" and r.json()["notes"] == "Strong FastAPI answers"
    db.expire_all()
    after = db.get(EvaluationScore, before.id)
    assert after.composite_score == before.composite_score  # extra fields ignored: scores are read-only
    assert (
        client.patch(f"/api/applications/{ids[0]}/decision", json={"decision": "hired"}, headers=recruiter).status_code
        == 422
    )


def _eval_id(db, app_id):
    return str(db.get(Application, uuid.UUID(app_id)).evaluation.id)


def test_stats(client, recruiter, job, db):
    _setup(client, recruiter, job, db)
    s = client.get(f"/api/jobs/{job['id']}/stats", headers=recruiter).json()
    assert s["total"] == 3 and s["evaluated"] == 1 and s["screened"] == 3
    assert s["by_stage"]["not_qualified"] == 1
    assert sum(b["count"] for b in s["histogram"]) == 3 and s["avg_composite"] > 0
    mine = client.get("/api/jobs/mine", headers=recruiter).json()[0]
    assert mine["applicant_count"] == 3 and mine["evaluated_count"] == 1 and mine["avg_score"] == s["avg_composite"]


def test_csv_export(client, recruiter, job, db):
    _, ids = _setup(client, recruiter, job, db)
    r = client.get(f"/api/jobs/{job['id']}/export", params={"format": "csv"}, headers=recruiter)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    lines = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert lines[0][0].startswith("Job: ")
    header, body = lines[1], lines[2:]
    assert header[0] == "Rank" and header[10] == "Composite /100"
    assert [row[1] for row in body] == ["Strong One", "Medium Two", "Weak Three"]
    assert float(body[0][10]) >= float(body[1][10])

    client.patch(f"/api/applications/{ids[1]}/decision", json={"decision": "shortlisted"}, headers=recruiter)
    r = client.get(
        f"/api/jobs/{job['id']}/export", params={"format": "csv", "only_shortlisted": True}, headers=recruiter
    )
    body = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))[2:]
    assert [row[1] for row in body] == ["Medium Two"]


def test_pdf_export(client, recruiter, job, db):
    _setup(client, recruiter, job, db)
    r = client.get(f"/api/jobs/{job['id']}/export", params={"format": "pdf"}, headers=recruiter)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert client.get(f"/api/jobs/{job['id']}/export", params={"format": "xls"}, headers=recruiter).status_code == 422


def test_recruiter_overview(client, recruiter, recruiter2, candidate, job, db):
    _setup(client, recruiter, job, db)
    o = client.get("/api/dashboard/overview", headers=recruiter).json()
    assert o["jobs_total"] == 1 and o["jobs_active"] == 1 and o["applications_total"] == 3
    assert o["evaluated"] == 1 and o["interviews_pending"] == 1
    assert len(o["recent"]) == 3 and o["awaiting_decision"][0]["full_name"] == "Strong One"
    assert o["avg_composite"] is not None
    empty = client.get("/api/dashboard/overview", headers=recruiter2).json()
    assert empty["applications_total"] == 0 and empty["recent"] == []
    assert client.get("/api/dashboard/overview", headers=candidate).status_code == 403
