"""Test setup: SQLite in-memory DB, local temp storage, console email, AI mock mode, no retry waits."""

import io
import json
import os
import tempfile

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "AI_MOCK": "true",
        "LLM_API_KEY": "",
        "STORAGE_BACKEND": "local",
        "LOCAL_STORAGE_DIR": tempfile.mkdtemp(prefix="recruiter-test-"),
        "EMAIL_BACKEND": "console",
        "JWT_SECRET": "test-secret",
        "BCRYPT_ROUNDS": "4",
        "CHECK_RESUME_NAME": "false",  # test resumes use other names; test_apply_checks.py turns it on
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from tenacity import wait_none  # noqa: E402

from app import database  # noqa: E402
from app.ai import client as ai_client  # noqa: E402
from app.core.limiter import limiter  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.notification import get_email_service  # noqa: E402

ai_client.WAIT_STRATEGY = wait_none()
ai_client.RESPECT_RATE_LIMIT_DELAY = False

STRONG_RESUME = """Ali Khan - Backend Developer
Email: ali@example.com
SUMMARY: Backend developer with 3 years of experience building REST APIs in Python.
SKILLS: Python, FastAPI, Django, PostgreSQL, SQL, Git, Docker, Redis, pytest, Linux
EXPERIENCE: Software Engineer at TechCorp (2021-2024) - 3 years. Built FastAPI microservices,
designed PostgreSQL schemas, containerised services with Docker, set up CI with GitHub Actions.
EDUCATION: Bachelor of Science in Computer Science (BSCS), Lahore Garrison University, 2021.
CERTIFICATIONS: certified AWS cloud practitioner"""

WEAK_RESUME = """Sara Ahmed - Marketing Executive
SUMMARY: Marketing professional with 4 years of experience in social media campaigns and sales.
SKILLS: Marketing, Photoshop, Excel, Communication, Sales, Content writing, Event management.
EXPERIENCE: Marketing Executive at BrandCo (2020-2024), ran campaigns, managed budgets and reports.
EDUCATION: Bachelor of Business Administration, University of the Punjab."""


def make_pdf(text: str | None) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    if text:
        y = 800
        for line in text.splitlines():
            c.drawString(40, y, line[:110])
            y -= 16
    else:
        c.rect(100, 500, 200, 200, fill=1)  # an image-like page with no text
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture()
def engine():
    eng = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db_session_factory(engine, monkeypatch):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", factory)
    return factory


@pytest.fixture()
def db(db_session_factory):
    s = db_session_factory()
    yield s
    s.close()


@pytest.fixture()
def emails():
    service = get_email_service()
    service.sent.clear()
    return service.sent


@pytest.fixture()
def client(db_session_factory, emails):
    def override_get_db():
        s = db_session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    limiter.reset()
    # Act like one browser: remember the device token each interview start returns and send it afterwards.
    # A test can leave it out with the header "x-test-no-device".
    devices: dict[str, str] = {}

    def on_request(request):
        parts = request.url.path.split("/")
        if len(parts) > 3 and parts[2] == "interviews" and "x-interview-device" not in request.headers:
            if request.headers.get("x-test-no-device"):
                return
            token = devices.get(parts[3])
            if token:
                request.headers["X-Interview-Device"] = token

    def on_response(response):
        parts = response.request.url.path.split("/")
        if len(parts) > 4 and parts[2] == "interviews" and parts[4] == "start" and response.status_code == 200:
            response.read()
            token = response.json().get("device_token")
            if token:
                devices[parts[3]] = token

    with TestClient(app) as c:
        c.event_hooks = {"request": [on_request], "response": [on_response]}
        yield c
    app.dependency_overrides.clear()


TINY_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200

PROFILE = {
    "phone": "+92 300 1234567",
    "city": "Lahore",
    "headline": "Backend developer",
}


def complete_profile(client, headers, **overrides):
    r = client.put("/api/profile/me", json={**PROFILE, **overrides}, headers=headers)
    assert r.status_code == 200, r.text
    r = client.post("/api/profile/me/photo", files={"image": ("me.jpg", TINY_JPEG, "image/jpeg")}, headers=headers)
    assert r.status_code == 200, r.text
    pdf = make_pdf(STRONG_RESUME)
    r = client.post("/api/profile/me/resume", files={"resume": ("cv.pdf", pdf, "application/pdf")}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["complete"], r.json()["missing"]
    return r.json()


def register(client, email, role, password="Passw0rd!", name="Test User", profile=True):
    r = client.post("/api/auth/register", json={"full_name": name, "email": email, "password": password, "role": role})
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    if role == "candidate" and profile:
        complete_profile(client, headers)
    return headers


@pytest.fixture()
def recruiter(client):
    return register(client, "rec@test.com", "recruiter", name="Rita Recruiter")


@pytest.fixture()
def recruiter2(client):
    return register(client, "rec2@test.com", "recruiter", name="Other Recruiter")


@pytest.fixture()
def candidate(client):
    return register(client, "cand@test.com", "candidate", name="Ali Khan")


@pytest.fixture()
def candidate2(client):
    return register(client, "cand2@test.com", "candidate", name="Sara Ahmed")


JOB_PAYLOAD = {
    "title": "Junior Python Backend Developer",
    "description": "Build and maintain REST APIs with FastAPI and PostgreSQL for our hiring platform.",
    "required_skills": ["Python", "FastAPI", "SQL", "Git", "Docker"],
    "min_experience_years": 1,
    "education_level": "bachelors",
    "screening_threshold": 40,
    "num_questions": 5,
    "seconds_per_question": 120,
    "follow_up_questions": 0,  # test_interview_integrity.py covers live follow-ups
}


@pytest.fixture()
def job(client, recruiter):
    r = client.post("/api/jobs", json=JOB_PAYLOAD, headers=recruiter)
    assert r.status_code == 201, r.text
    return r.json()


DEFAULT_ANSWERS = {"total_experience": "2", "highest_degree": "Bachelor's", "cgpa": "3.4 / 4.0"}


def apply(client, headers, job_id, pdf: bytes, filename="resume.pdf", ctype="application/pdf", answers=None):
    return client.post(
        f"/api/jobs/{job_id}/apply",
        files={"resume": (filename, pdf, ctype)},
        data={"answers": json.dumps(DEFAULT_ANSWERS if answers is None else answers)},
        headers=headers,
    )
