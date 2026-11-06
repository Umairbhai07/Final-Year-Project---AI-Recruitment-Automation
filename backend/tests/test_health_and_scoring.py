from app.services import evaluation


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "ai_mock" in r.json()


def test_docs_available(client):
    assert client.get("/docs").status_code == 200
    assert "/api/jobs" in client.get("/openapi.json").json()["paths"]


def test_resume_total():
    assert evaluation.resume_total(32, 20, 10) == 62


def test_answer_score_weights():
    assert evaluation.answer_score(10, 10, 10) == 10
    assert evaluation.answer_score(8, 6, 4) == round(0.5 * 8 + 0.3 * 6 + 0.2 * 4, 1) == 6.6


def test_interview_score_mean_scaled_to_30():
    assert evaluation.interview_score([10, 10, 10]) == 30
    assert evaluation.interview_score([5, 7, 6]) == 18.0
    assert evaluation.interview_score([6.6, 3.1, 8.0]) == round((6.6 + 3.1 + 8.0) / 3 / 10 * 30, 1)
    assert evaluation.interview_score([]) == 0


def test_composite():
    assert evaluation.composite_score(55, 21.5) == 76.5
    assert evaluation.composite_score(55, None) == 55
