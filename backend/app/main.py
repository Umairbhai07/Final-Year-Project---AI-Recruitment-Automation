"""FastAPI application factory: CORS, routers, rate limiter, error handlers, /health."""

import logging
from contextlib import asynccontextmanager

import anyio.to_thread
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.ai.client import AIServiceError
from app.config import settings
from app.core.limiter import limiter
from app.database import pool_limit
from app.routers import applications, auth, dashboard, interviews, jobs, profile, reports

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


def _check_production() -> None:
    """Refuse to start a production server with settings that would make it insecure or broken."""
    if settings.APP_ENV != "production":
        return
    problems = []
    if settings.JWT_SECRET in ("", "change-me") or len(settings.JWT_SECRET) < 32:
        problems.append("JWT_SECRET must be a long random value (at least 32 characters)")
    if settings.DATABASE_URL.startswith("sqlite"):
        problems.append("DATABASE_URL must point to Postgres (Supabase), not SQLite")
    if settings.STORAGE_BACKEND != "supabase":
        log.warning("STORAGE_BACKEND is %r: uploaded files are lost when the server restarts", settings.STORAGE_BACKEND)
    if problems:
        raise RuntimeError("Unsafe production settings: " + "; ".join(problems))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Our endpoints are normal (sync) functions, so FastAPI runs each in a worker thread (40 by default). If there
    # are more threads than database connections, threads wait for a connection while the threads holding one
    # wait for a free thread to finish, and the server freezes. The load test found this at 1000 users, so allow
    # only as many threads as connections: extra requests then simply wait their turn.
    limit = pool_limit()
    if limit:
        anyio.to_thread.current_default_thread_limiter().total_tokens = limit
    yield


def create_app() -> FastAPI:
    _check_production()
    app = FastAPI(
        lifespan=lifespan,
        title="AI Recruitment Assistant API",
        version="1.0.0",
        description="API for the AI Recruitment Assistant.",
    )
    app.state.limiter = limiter

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(status_code=429, content={"detail": "Too many requests. Please try again later."})

    @app.exception_handler(AIServiceError)
    async def ai_error_handler(request: Request, exc: AIServiceError):
        return JSONResponse(status_code=502, content={"detail": f"AI service error: {exc}"})

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok", "ai_mock": settings.ai_mock_effective}

    for module in (auth, jobs, applications, dashboard, interviews, reports, profile):
        app.include_router(module.router, prefix="/api")

    if settings.ai_mock_effective:
        log.warning("AI mock mode is ON (AI_MOCK=true or no LLM_API_KEY). AI results are simulated.")
    return app


app = create_app()
