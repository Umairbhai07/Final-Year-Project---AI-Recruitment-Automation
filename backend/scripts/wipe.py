"""Deletes EVERYTHING: all accounts, jobs, applications, interviews, the AI audit log, and every stored file
(resumes, photos, recordings, webcam snapshots). The tables themselves stay, so the site keeps working, empty.

Run from backend/ (it uses the database and storage in backend/.env):
    python -m scripts.wipe            # asks you to type DELETE first
    python -m scripts.wipe --yes      # no question (for scripts)
Then, if you want the demo accounts back:  python -m scripts.seed
"""

import argparse
import re

from sqlalchemy import text

import app.models  # noqa: F401  (registers every table)
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.storage import get_storage


def where() -> str:
    db = re.sub(r"//[^@/]*@", "//", settings.DATABASE_URL)  # hide the password
    files = settings.SUPABASE_URL if settings.STORAGE_BACKEND == "supabase" else settings.LOCAL_STORAGE_DIR
    return f"  Database: {db}\n  Files:    {settings.STORAGE_BACKEND} ({files})"


def wipe() -> None:
    tables = [t.name for t in Base.metadata.sorted_tables]
    db = SessionLocal()
    try:
        counts = {t: db.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() for t in tables}
        if engine.dialect.name == "postgresql":
            # TRUNCATE also clears the insert-only audit log: its trigger only blocks row UPDATE and DELETE.
            db.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE"))
        else:
            for t in reversed(tables):
                db.execute(text(f'DELETE FROM "{t}"'))
        db.commit()
    finally:
        db.close()
    for t, n in counts.items():
        if n:
            print(f"  deleted {n:>6} rows from {t}")
    files = get_storage().delete_all()
    print(f"  deleted {files:>6} stored files")
    print("Done. Everything is empty. Run `python -m scripts.seed` if you want the demo accounts back.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Delete all data and files")
    ap.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    args = ap.parse_args()
    print("This deletes ALL accounts, jobs, applications, interviews and files in:\n" + where())
    if not args.yes and input("Type DELETE to continue: ").strip() != "DELETE":
        print("Cancelled. Nothing was deleted.")
        return
    wipe()


if __name__ == "__main__":
    main()
