"""Checks that the database and every external service in backend/.env actually work.

Run from backend/:   python -m scripts.check_setup
Nothing is changed except one tiny test file that is uploaded and deleted again in Supabase Storage.
"""

import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.config import settings

OK, WARN, FAIL = "\033[32m✔\033[0m", "\033[33m!\033[0m", "\033[31m✘\033[0m"
problems = 0


def report(symbol: str, title: str, detail: str = "") -> None:
    global problems
    if symbol == FAIL:
        problems += 1
    print(f"  {symbol} {title}" + (f"\n      {detail}" if detail else ""))


def mask(url: str) -> str:
    """Hide the password in a database URL before printing it."""
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds, host = rest.rsplit("@", 1)
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:****@{host}"


def check_database() -> None:
    print("\nDatabase")
    url = settings.DATABASE_URL
    print(f"  using {mask(url)}")
    if url.startswith("sqlite"):
        report(WARN, "SQLite (local file) is fine for trying the app. Use Supabase Postgres for the real setup.")
    elif "supabase" in url and not url.startswith("postgresql+psycopg://"):
        report(
            FAIL,
            "The URL must start with postgresql+psycopg://",
            "Replace 'postgresql://' or 'postgres://' at the start.",
        )
        return
    try:
        engine = create_engine(url, connect_args={"prepare_threshold": None} if "psycopg" in url else {})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            tables = set(inspect(conn).get_table_names())
        report(OK, "Connected")
    except Exception as exc:  # show the real reason in plain words
        msg = str(exc).splitlines()[0]
        hint = ""
        if "password authentication failed" in msg:
            hint = "Wrong database password. Supabase → Project Settings → Database → Reset database password."
        elif "could not translate host name" in msg or "Network is unreachable" in msg or "timeout" in msg.lower():
            hint = "Can't reach the server. Use the Session pooler connection string (Supabase → Connect)."
        report(FAIL, f"Could not connect: {msg}", hint)
        return
    if {"users", "jobs", "applications"} <= tables:
        report(OK, "Tables exist (migrations applied)")
        with engine.connect() as conn:
            users = conn.execute(text("SELECT count(*) FROM users")).scalar()
        report(
            OK if users else WARN,
            f"{users} users in the database",
            "" if users else "Run: python -m scripts.seed --reset   to add demo data",
        )
    else:
        report(FAIL, "Tables are missing", "Run: alembic upgrade head")


def check_ai() -> None:
    print("\nAI (Groq)")
    if settings.ai_mock_effective:
        report(
            WARN,
            "Mock AI is ON: results are simulated",
            "To use real AI set LLM_API_KEY and STT_API_KEY (from https://console.groq.com/keys) and AI_MOCK=false",
        )
        return
    import openai

    from app.ai import client as ai

    try:
        resp = ai._chat_completion(
            temperature=0, max_tokens=300, messages=[{"role": "user", "content": "Reply with the word OK"}]
        )
        used = ai._working_model
        report(OK, f"Language model works ({used}): {(resp.choices[0].message.content or '').strip()!r}")
        if used != settings.LLM_MODEL:
            report(
                WARN,
                f"'{settings.LLM_MODEL}' is not available on Groq, so the app uses '{used}' automatically",
                f"Optional: set LLM_MODEL={used} in backend/.env to skip the check",
            )
    except Exception as exc:
        report(
            FAIL,
            f"Language model failed: {str(exc).splitlines()[0]}",
            "Check LLM_API_KEY. A 401 error means the key is wrong or was deleted.",
        )
    try:
        stt = openai.OpenAI(
            base_url=settings.STT_BASE_URL,
            api_key=settings.STT_API_KEY or settings.LLM_API_KEY,
            timeout=60,
            max_retries=0,
        )
        sample = Path(__file__).with_name("sample_answer.ogg")
        result = stt.audio.transcriptions.create(
            model=settings.STT_MODEL, file=(sample.name, sample.read_bytes()), response_format="json", language="en"
        )
        heard = (result.text or "").strip()
        if "python" in heard.lower() or "voice interview" in heard.lower():
            report(OK, f"Speech-to-text works ({settings.STT_MODEL})", f'Sample clip was heard as: "{heard}"')
        else:
            report(WARN, "Speech-to-text answered, but the sample text looks wrong", f'Heard: "{heard}"')
    except Exception as exc:
        report(
            FAIL,
            f"Speech-to-text failed: {str(exc).splitlines()[0]}",
            "Check STT_API_KEY (the Groq key) and STT_MODEL=whisper-large-v3",
        )


def check_storage() -> None:
    print("\nFile storage")
    if settings.STORAGE_BACKEND != "supabase":
        report(
            OK,
            f"Local folder: {settings.LOCAL_STORAGE_DIR}",
            "For deployment set STORAGE_BACKEND=supabase with SUPABASE_URL and SUPABASE_SERVICE_KEY",
        )
        return
    from app.services.storage import SupabaseStorage

    key = f"_setup_check/{uuid.uuid4()}.txt"
    try:
        store = SupabaseStorage(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY, settings.SUPABASE_BUCKET)
        store.save(key, b"ok", "text/plain")
        assert store.load(key) == b"ok"
        store.delete(key)
        report(OK, f"Supabase bucket '{settings.SUPABASE_BUCKET}' upload/download works")
    except Exception as exc:
        report(
            FAIL,
            f"Supabase storage failed: {str(exc).splitlines()[0]}",
            "Check SUPABASE_URL, SUPABASE_SERVICE_KEY (the service_role key) and that the bucket exists.",
        )


def check_email() -> None:
    print("\nEmail")
    if settings.EMAIL_BACKEND != "resend":
        report(OK, "Console mode: emails are printed in the backend terminal (fine for the demo)")
        return
    if not settings.RESEND_API_KEY:
        report(FAIL, "EMAIL_BACKEND=resend but RESEND_API_KEY is empty")
        return
    import httpx

    try:
        r = httpx.get(
            "https://api.resend.com/domains", headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"}, timeout=20
        )
        if r.status_code == 200:
            report(OK, "Resend key works", "Without a verified domain Resend only delivers to your own account email.")
        else:
            report(FAIL, f"Resend rejected the key (HTTP {r.status_code})")
    except Exception as exc:
        report(FAIL, f"Could not reach Resend: {exc}")


def check_security() -> None:
    print("\nSecurity")
    if settings.JWT_SECRET in ("change-me", "", "test-secret") or len(settings.JWT_SECRET) < 32:
        report(
            WARN if settings.APP_ENV != "production" else FAIL,
            "JWT_SECRET is weak or the default",
            "Generate one with:  openssl rand -hex 32",
        )
    else:
        report(OK, "JWT_SECRET is set")


if __name__ == "__main__":
    print("AI Recruitment Assistant: setup check")
    check_database()
    check_ai()
    check_storage()
    check_email()
    check_security()
    print(
        "\n"
        + ("All good!" if problems == 0 else f"{problems} problem(s) found. Fix them in backend/.env and run again.")
    )
    sys.exit(1 if problems else 0)
