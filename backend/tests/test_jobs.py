from datetime import date, timedelta

from tests.conftest import JOB_PAYLOAD


def test_candidate_cannot_create_job_403(client, candidate):
    assert client.post("/api/jobs", json=JOB_PAYLOAD, headers=candidate).status_code == 403


def test_create_and_get_job(client, recruiter, job):
    assert job["status"] == "active" and job["required_skills"] == JOB_PAYLOAD["required_skills"]
    r = client.get(f"/api/jobs/{job['id']}", headers=recruiter)
    assert r.status_code == 200 and r.json()["title"] == JOB_PAYLOAD["title"]


def test_job_validation(client, recruiter):
    bad = {**JOB_PAYLOAD, "screening_threshold": 80}
    assert client.post("/api/jobs", json=bad, headers=recruiter).status_code == 422
    bad = {**JOB_PAYLOAD, "num_questions": 9}
    assert client.post("/api/jobs", json=bad, headers=recruiter).status_code == 422
    bad = {**JOB_PAYLOAD, "required_skills": []}
    assert client.post("/api/jobs", json=bad, headers=recruiter).status_code == 422


def test_other_recruiter_gets_404(client, recruiter2, job):
    assert client.get(f"/api/jobs/{job['id']}", headers=recruiter2).status_code == 404
    assert client.patch(f"/api/jobs/{job['id']}", json={"title": "Hacked title"}, headers=recruiter2).status_code == 404
    assert (
        client.patch(f"/api/jobs/{job['id']}/status", json={"status": "closed"}, headers=recruiter2).status_code == 404
    )


def test_mine_lists_own_jobs_with_counts(client, recruiter, recruiter2, job):
    r = client.get("/api/jobs/mine", headers=recruiter)
    assert r.status_code == 200
    assert [j["id"] for j in r.json()] == [job["id"]]
    assert r.json()[0]["applicant_count"] == 0
    assert client.get("/api/jobs/mine", headers=recruiter2).json() == []


def test_update_job(client, recruiter, job):
    r = client.patch(
        f"/api/jobs/{job['id']}", json={"title": "Python Developer", "required_skills": ["Python"]}, headers=recruiter
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Python Developer" and r.json()["required_skills"] == ["Python"]


def test_status_transitions(client, recruiter, job):
    url = f"/api/jobs/{job['id']}/status"
    assert client.patch(url, json={"status": "paused"}, headers=recruiter).json()["status"] == "paused"
    assert client.patch(url, json={"status": "active"}, headers=recruiter).json()["status"] == "active"
    assert client.patch(url, json={"status": "closed"}, headers=recruiter).json()["status"] == "closed"
    # closed is final
    assert client.patch(url, json={"status": "active"}, headers=recruiter).status_code == 409
    assert client.patch(url, json={"status": "paused"}, headers=recruiter).status_code == 409
    # closed job cannot be edited
    assert client.patch(f"/api/jobs/{job['id']}", json={"title": "New title"}, headers=recruiter).status_code == 409


def test_candidates_only_see_active_jobs(client, recruiter, candidate, job):
    assert [j["id"] for j in client.get("/api/jobs", headers=candidate).json()] == [job["id"]]
    client.patch(f"/api/jobs/{job['id']}/status", json={"status": "paused"}, headers=recruiter)
    assert client.get("/api/jobs", headers=candidate).json() == []
    assert client.get(f"/api/jobs/{job['id']}", headers=candidate).status_code == 404


def test_search_by_title_and_skill(client, recruiter, candidate, job):
    other = {**JOB_PAYLOAD, "title": "Frontend React Developer", "required_skills": ["React", "TypeScript"]}
    client.post("/api/jobs", json=other, headers=recruiter)
    titles = lambda q: [j["title"] for j in client.get("/api/jobs", params={"q": q}, headers=candidate).json()]  # noqa
    assert titles("react") == ["Frontend React Developer"]
    assert titles("fastapi") == [JOB_PAYLOAD["title"]]
    assert len(titles("")) == 2


def test_past_deadline_jobs_hidden(client, recruiter, candidate):
    payload = {**JOB_PAYLOAD, "deadline": (date.today() - timedelta(days=1)).isoformat()}
    client.post("/api/jobs", json=payload, headers=recruiter)
    assert client.get("/api/jobs", headers=candidate).json() == []
