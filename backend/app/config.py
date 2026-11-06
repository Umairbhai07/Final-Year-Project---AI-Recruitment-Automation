"""Application configuration loaded from environment variables (.env)."""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/recruiter"
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_HOURS: int = 24
    JWT_REFRESH_DAYS: int = 7
    CORS_ORIGINS: str = "http://localhost:5173"

    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    STT_BASE_URL: str = "https://api.groq.com/openai/v1"
    STT_API_KEY: str = ""
    STT_MODEL: str = "whisper-large-v3"
    AI_MOCK: bool = False
    AI_TIMEOUT_SECONDS: int = 60

    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_DIR: str = "./storage"
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_BUCKET: str = "recruiter-files"

    EMAIL_BACKEND: str = "console"
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "onboarding@resend.dev"
    # EMAIL_BACKEND=smtp sends through any mail server, e.g. Gmail: smtp.gmail.com, port 465, your Gmail address
    # and a Gmail "App password" (Google account, Security, 2-Step Verification, App passwords).
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FRONTEND_URL: str = "http://localhost:5173"
    # When true, new accounts must click the link in the welcome email before applying or posting jobs.
    # Turn it on only after real email delivery works (EMAIL_BACKEND=resend with a verified domain).
    REQUIRE_EMAIL_VERIFICATION: bool = False
    # Reject a resume whose text does not contain the candidate's own name (someone else's resume).
    CHECK_RESUME_NAME: bool = True
    # Per-IP request limits (login, register, apply, uploads). Only turn off for a local load test, where every
    # simulated user comes from the same IP address.
    RATE_LIMIT_ENABLED: bool = True
    # Database connections per server process (not used on Vercel, which keeps 2 to 5 per function instance).
    # Keep workers x (DB_POOL_SIZE + DB_MAX_OVERFLOW) under the database's connection limit.
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 10

    BCRYPT_ROUNDS: int = 10  # 10 is the OWASP minimum and keeps login/sign-up quick; tests lower it further
    # Serverless hosting (Vercel sets VERCEL=1): no work may run after the response, so resume screening runs
    # inside the request, and database connections are not kept open between requests.
    SERVERLESS: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def serverless(self) -> bool:
        return self.SERVERLESS or os.environ.get("VERCEL") == "1"

    @property
    def ai_mock_effective(self) -> bool:
        """Mock mode is on if requested explicitly OR no LLM key is configured."""
        return self.AI_MOCK or not self.LLM_API_KEY


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
