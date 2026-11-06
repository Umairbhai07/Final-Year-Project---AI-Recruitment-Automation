"""Database engine, session factory and the FastAPI dependency that yields a session."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def pool_limit() -> int | None:
    """How many database connections one server process may hold (None for SQLite, which has no limit)."""
    if not settings.DATABASE_URL.startswith("postgresql"):
        return None
    return 5 if settings.serverless else settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW


def _make_engine(url: str):
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    elif url.startswith("postgresql+psycopg"):
        # Supabase's connection pooler (PgBouncer/Supavisor in transaction mode) does not support
        # server-side prepared statements, so turn psycopg's automatic preparing off.
        kwargs["connect_args"] = {"prepare_threshold": None}
        if settings.serverless:
            # A warm function instance serves many requests, so keep one or two connections open instead of
            # reconnecting (TLS + login) on every request. Recycle them before the pooler drops idle ones.
            kwargs.update(pool_size=2, max_overflow=3, pool_recycle=240, pool_timeout=10)
        else:
            # A normal server process: enough connections for its request threads, and fail after 10 s instead
            # of letting requests pile up for 30 s when the database is overloaded.
            kwargs.update(pool_size=settings.DB_POOL_SIZE, max_overflow=settings.DB_MAX_OVERFLOW, pool_timeout=10)
    return create_engine(url, **kwargs)


engine = _make_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
