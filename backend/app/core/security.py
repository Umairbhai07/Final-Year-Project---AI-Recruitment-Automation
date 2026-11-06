"""Password hashing (bcrypt) and JWT creation/verification."""

import hashlib
import hmac
import secrets
import time
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.now(UTC) + timedelta(hours=settings.JWT_ACCESS_HOURS)
    payload = {"sub": user_id, "role": role, "type": "access", "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload


RESET_MINUTES = 30


def _password_fingerprint(password_hash: str) -> str:
    # Part of the reset token: once the password changes, every older reset link stops working.
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def create_reset_token(user_id: str, password_hash: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=RESET_MINUTES)
    payload = {"sub": user_id, "type": "reset", "pwd": _password_fingerprint(password_hash), "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_reset_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    return payload if payload.get("type") == "reset" else None


def reset_token_matches(payload: dict, password_hash: str) -> bool:
    return secrets.compare_digest(payload.get("pwd", ""), _password_fingerprint(password_hash))


VERIFY_DAYS = 3


def create_verify_token(user_id: str, email: str) -> str:
    expire = datetime.now(UTC) + timedelta(days=VERIFY_DAYS)
    payload = {"sub": user_id, "type": "verify", "email": email, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_verify_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    return payload if payload.get("type") == "verify" else None


def new_refresh_token() -> str:
    """Refresh tokens are random strings; only their SHA-256 hash is stored in the DB."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# --- 6-digit email codes (forgot password, change password) ----------------------------------------------------
# No table is needed: the code is derived from the user, the purpose, the current password and a 10-minute window.
# Changing the password changes the code, so a code works only once. Wrong guesses are limited per email.
CODE_WINDOW_SECONDS = 600
CODE_MINUTES = CODE_WINDOW_SECONDS // 60


def _code_for(user_id: str, purpose: str, password_hash: str, window: int) -> str:
    msg = f"code:{purpose}:{user_id}:{_password_fingerprint(password_hash)}:{window}"
    digest = hmac.new(settings.JWT_SECRET.encode(), msg.encode(), hashlib.sha256).digest()
    return f"{int.from_bytes(digest[:8], 'big') % 1_000_000:06d}"


def create_code(user_id: str, purpose: str, password_hash: str, now: float | None = None) -> str:
    return _code_for(user_id, purpose, password_hash, int((now or time.time()) // CODE_WINDOW_SECONDS))


def code_matches(code: str, user_id: str, purpose: str, password_hash: str, now: float | None = None) -> bool:
    """True for the code of this window or the one before (so a code is good for 10 to 20 minutes)."""
    window = int((now or time.time()) // CODE_WINDOW_SECONDS)
    code = (code or "").strip()
    return any(hmac.compare_digest(code, _code_for(user_id, purpose, password_hash, w)) for w in (window, window - 1))
