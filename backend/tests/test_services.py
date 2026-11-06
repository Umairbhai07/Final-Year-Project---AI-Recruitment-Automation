import os
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from app.ai.mock import mock_answer_eval, mock_questions, mock_resume_screen
from app.models import Application
from app.models.enums import Stage
from app.services import notification
from app.services.application import InvalidTransition, set_stage
from app.services.resume import extract_text
from app.services.storage import LocalStorage, StorageError
from tests.conftest import STRONG_RESUME, make_pdf


def test_stage_state_machine():
    a = Application(stage=Stage.SUBMITTED.value)
    set_stage(a, Stage.UNDER_REVIEW)
    set_stage(a, Stage.INTERVIEW_INVITED)
    set_stage(a, Stage.INTERVIEW_IN_PROGRESS)
    set_stage(a, Stage.EVALUATED)
    with pytest.raises(InvalidTransition):
        set_stage(a, Stage.UNDER_REVIEW)
    b = Application(stage=Stage.SUBMITTED.value)
    with pytest.raises(InvalidTransition):
        set_stage(b, Stage.EVALUATED)


def test_local_storage_roundtrip_and_traversal(tmp_path):
    s = LocalStorage(str(tmp_path))
    s.save("a/b.pdf", b"data", "application/pdf")
    assert s.load("a/b.pdf") == b"data"
    s.delete("a/b.pdf")
    with pytest.raises(StorageError):
        s.load("a/b.pdf")
    with pytest.raises(StorageError):
        s.save("../escape.txt", b"x", "text/plain")


def test_extract_text():
    assert "FastAPI" in extract_text(make_pdf(STRONG_RESUME))
    assert extract_text(make_pdf(None)) == ""
    assert extract_text(b"%PDF-garbage") == ""


def test_resend_backend_sends_and_never_raises(monkeypatch):
    sent = []

    class FakeEmails:
        @staticmethod
        def send(payload):
            sent.append(payload)
            if payload["to"] == ["boom@test.com"]:
                raise RuntimeError("resend down")

    svc = notification.ResendEmailService("key", "from@test.com")
    monkeypatch.setattr(svc, "_resend", SimpleNamespace(Emails=FakeEmails))
    notification.Notifier(svc).interview_invitation("x@test.com", "<b>Ali</b>", "Dev", "sid-1")
    assert sent[0]["from"] == "from@test.com" and "/interview/sid-1" in sent[0]["html"]
    assert "<b>Ali</b>" not in sent[0]["html"]  # user text is HTML-escaped
    notification.Notifier(svc).interview_completed("boom@test.com", "A", "Dev")  # no exception


def test_mock_ai_is_deterministic():
    job = SimpleNamespace(
        title="Dev",
        required_skills=["Python", "Postgres", "ReactJS"],
        min_experience_years=2,
        education_level="bachelors",
    )
    text = "python developer, postgresql and react.js, 2 years, BSc computer science"
    a, b = mock_resume_screen(job, text), mock_resume_screen(job, text)
    assert a == b
    assert a["matched_skills"] == ["Python", "Postgres", "ReactJS"]  # synonyms count
    assert a["skill_score"] == 40 and a["experience_score"] == 20 and a["education_score"] == 10
    qs = mock_questions(job, a, 6)["questions"]
    assert len(qs) == 6 and qs[-1]["focus"] == "Behavioural"
    ev = mock_answer_eval(job, qs[0], "I built a Python project and designed tests because I learned a lot")
    assert 0 <= ev["accuracy"] <= 10


@pytest.mark.skipif(not os.environ.get("PG_TEST_URL"), reason="set PG_TEST_URL to test the Postgres trigger")
def test_postgres_audit_log_is_insert_only():
    eng = create_engine(os.environ["PG_TEST_URL"])
    with eng.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO ai_audit_log (id, kind, model, input, created_at) "
                "VALUES (gen_random_uuid(), 'test', 'm', 'i', now())"
            )
        )
        conn.commit()
        for stmt in ("UPDATE ai_audit_log SET kind = 'x'", "DELETE FROM ai_audit_log"):
            with pytest.raises(Exception, match="insert-only"):
                conn.execute(text(stmt))
            conn.rollback()


def test_supabase_storage_rest_calls():
    """The Storage REST client sends the key in both headers (works with sb_secret_ and legacy keys)."""
    import httpx

    from app.services.storage import StorageError, SupabaseStorage

    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.method, str(req.url), req.headers.get("apikey"), req.headers.get("authorization")))
        if req.method == "GET" and req.url.path.endswith("missing.pdf"):
            return httpx.Response(400, json={"message": "Object not found"})
        if req.method == "GET":
            return httpx.Response(200, content=b"data")
        return httpx.Response(200, json={"Key": "x"})

    store = SupabaseStorage("https://proj.supabase.co/", "sb_secret_abc", "recruiter-files")
    store.client = httpx.Client(transport=httpx.MockTransport(handler), headers=store.client.headers)
    assert store.save("resumes/a b.pdf", b"%PDF", "application/pdf") == "resumes/a b.pdf"
    assert store.load("resumes/a b.pdf") == b"data"
    store.delete("resumes/a b.pdf")
    try:
        store.load("resumes/missing.pdf")
        raise AssertionError("expected StorageError")
    except StorageError as exc:
        assert "Object not found" in str(exc)
    assert seen[0] == (
        "POST",
        "https://proj.supabase.co/storage/v1/object/recruiter-files/resumes/a%20b.pdf",
        "sb_secret_abc",
        "Bearer sb_secret_abc",
    )
    assert seen[2][0] == "DELETE" and seen[2][1].endswith("/object/recruiter-files")


def test_supabase_delete_all_walks_folders():
    """scripts/wipe.py: every file in the bucket is listed (folders included) and deleted."""
    import json

    import httpx

    from app.services.storage import SupabaseStorage

    tree = {"": ["resumes/", "profiles/"], "resumes": ["a.pdf", "b.pdf"], "profiles": ["u1/"], "profiles/u1": ["p.jpg"]}
    deleted = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        if req.method == "POST" and "/list/" in req.url.path:
            items = tree.get(body["prefix"], [])
            return httpx.Response(
                200, json=[{"name": n.rstrip("/"), "id": None if n.endswith("/") else "x"} for n in items]
            )
        deleted.extend(body["prefixes"])
        return httpx.Response(200, json=[])

    store = SupabaseStorage("https://proj.supabase.co", "sb_secret_abc", "recruiter-files")
    store.client = httpx.Client(transport=httpx.MockTransport(handler), headers=store.client.headers)
    assert store.delete_all() == 3
    assert sorted(deleted) == ["profiles/u1/p.jpg", "resumes/a.pdf", "resumes/b.pdf"]


def test_local_delete_all(tmp_path):
    from app.services.storage import LocalStorage

    store = LocalStorage(str(tmp_path))
    store.save("resumes/x/a.pdf", b"1", "application/pdf")
    store.save("audio/b.webm", b"2", "audio/webm")
    assert store.delete_all() == 2
    assert not any(tmp_path.iterdir())


def test_smtp_email_service(monkeypatch):
    """EMAIL_BACKEND=smtp (e.g. Gmail with an App password) logs in and sends; a failure never raises."""
    import smtplib

    from app.services.notification import SmtpEmailService

    sent = []

    class FakeSMTP:
        def __init__(self, host, port, context=None, timeout=None):
            sent.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, user, password):
            sent.append(("login", user))

        def send_message(self, msg):
            sent.append(("send", msg["To"], msg["Subject"], msg["From"]))

    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    svc = SmtpEmailService("smtp.gmail.com", 465, "me@gmail.com", "app-pass", "onboarding@resend.dev")
    svc.send("you@test.com", "Your code", "<p>123456</p>")
    assert sent == [
        ("connect", "smtp.gmail.com", 465),
        ("login", "me@gmail.com"),
        ("send", "you@test.com", "Your code", "RecruitAI <me@gmail.com>"),
    ]

    def boom(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr(smtplib, "SMTP_SSL", boom)
    svc.send("you@test.com", "Your code", "<p>123456</p>")  # logged, not raised
