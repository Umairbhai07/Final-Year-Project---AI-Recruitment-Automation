"""Register, login (with failed-attempt lockout per IP), refresh-token rotation, logout and password reset."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import (
    CODE_MINUTES,
    code_matches,
    create_access_token,
    create_code,
    create_verify_token,
    decode_reset_token,
    decode_verify_token,
    hash_password,
    hash_token,
    new_refresh_token,
    reset_token_matches,
    verify_password,
)
from app.models import LoginAttempt, RefreshToken, User
from app.schemas.auth import LoginIn, RegisterIn
from app.services.notification import Notifier

DUPLICATE_EMAIL = "An account with this email already exists. Sign in, or use Forgot password if you can't."
MAX_FAILED_LOGINS = 10
FAILED_LOGIN_WINDOW = timedelta(minutes=15)


def _as_utc(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def register(db: Session, data: RegisterIn) -> User:
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE_EMAIL)
    user = User(
        full_name=data.full_name, email=data.email, password_hash=hash_password(data.password), role=data.role.value
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE_EMAIL) from None
    send_verification(user)
    return user


def send_verification(user: User) -> None:
    Notifier().verify_email(user.email, user.full_name, create_verify_token(str(user.id), user.email))


def verify_email(db: Session, token: str) -> User:
    payload = decode_verify_token(token)
    user = db.get(User, _uuid(payload.get("sub"))) if payload else None
    if user is None or payload.get("email") != user.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This link is invalid or has expired. Ask for a new one.")
    user.email_verified = True
    db.commit()
    return user


def require_verified(user: User) -> None:
    if settings.REQUIRE_EMAIL_VERIFICATION and not user.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Please confirm your email first. We sent you a link.")


def _issue_tokens(db: Session, user: User) -> tuple[str, str]:
    refresh = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh),
            expires_at=datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_DAYS),
        )
    )
    db.commit()
    return create_access_token(str(user.id), user.role), refresh


def failed_attempts(db: Session, ip: str) -> int:
    since = datetime.now(UTC) - FAILED_LOGIN_WINDOW
    return (
        db.scalar(
            select(func.count())
            .select_from(LoginAttempt)
            .where(LoginAttempt.ip_address == ip, LoginAttempt.created_at >= since)
        )
        or 0
    )


def login(db: Session, data: LoginIn, ip: str) -> tuple[User, str, str]:
    if failed_attempts(db, ip) >= MAX_FAILED_LOGINS:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed login attempts. Please wait 15 minutes and try again."
        )
    user = db.scalar(select(User).where(User.email == data.email))
    # Checking the password is slow on purpose (bcrypt). Hand the database connection back to the pool while it
    # runs, so many people signing in at once don't use up all connections (found in the load test).
    db.rollback()
    if user is None or not verify_password(data.password, user.password_hash):
        db.add(LoginAttempt(ip_address=ip, email=data.email))
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if data.role is not None and user.role != data.role.value:
        other = "Recruiter" if user.role == "recruiter" else "Candidate"
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, f"This is a {user.role} account. Switch to “{other}” to sign in."
        )
    access, refresh = _issue_tokens(db, user)
    return user, access, refresh


def _find_valid_refresh(db: Session, token: str) -> RefreshToken:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(token)))
    if row is None or row.revoked or _as_utc(row.expires_at) < datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")
    return row


def refresh(db: Session, token: str) -> tuple[User, str, str]:
    """Rotate: the old refresh token is revoked and a new pair is issued."""
    row = _find_valid_refresh(db, token)
    row.revoked = True
    user = row.user
    access, new_refresh = _issue_tokens(db, user)
    return user, access, new_refresh


def _revoke_all(db: Session, user: User) -> None:
    for t in user.refresh_tokens:
        t.revoked = True


MAX_CODE_TRIES = 5
WRONG_CODE = "That code is not correct or has expired. Check the latest email, or ask for a new code."


def forgot_password(db: Session, email: str) -> None:
    """Email a 6-digit reset code if the account exists. The response is the same either way, so nobody can test
    which emails have accounts."""
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        code = create_code(str(user.id), "reset", user.password_hash)
        Notifier().password_code(user.email, user.full_name, code, CODE_MINUTES, "reset")


def _check_code(db: Session, user: User | None, email: str, code: str, purpose: str) -> User:
    """Wrong codes are counted per email (in the failed-login table), so a code can't be guessed."""
    since = datetime.now(UTC) - FAILED_LOGIN_WINDOW
    tries = db.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(
            LoginAttempt.ip_address == f"code:{purpose}",
            LoginAttempt.email == email,
            LoginAttempt.created_at >= since,
        )
    )
    if (tries or 0) >= MAX_CODE_TRIES:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many wrong codes. Please wait 15 minutes and ask for a new code."
        )
    if user is None or not code_matches(code, str(user.id), purpose, user.password_hash):
        db.add(LoginAttempt(ip_address=f"code:{purpose}", email=email))
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, WRONG_CODE)
    return user


def reset_with_code(db: Session, email: str, code: str, password: str) -> User:
    user = _check_code(db, db.scalar(select(User).where(User.email == email)), email, code, "reset")
    user.password_hash = hash_password(password)
    _revoke_all(db, user)  # signed out everywhere
    db.commit()
    return user


def reset_password(db: Session, token: str, password: str) -> User:
    payload = decode_reset_token(token)
    user = db.get(User, _uuid(payload.get("sub"))) if payload else None
    if user is None or not reset_token_matches(payload, user.password_hash):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has expired. Please ask for a new one."
        )
    user.password_hash = hash_password(password)
    _revoke_all(db, user)  # signed out everywhere
    db.commit()
    return user


def send_change_code(user: User, current: str) -> None:
    """Step 1 of changing the password: check the current password, then email a code."""
    if not verify_password(current, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Your current password is not correct")
    code = create_code(str(user.id), "change", user.password_hash)
    Notifier().password_code(user.email, user.full_name, code, CODE_MINUTES, "change")


def change_password(db: Session, user: User, code: str, new: str) -> None:
    """Step 2: the code from the email and the new password."""
    _check_code(db, user, user.email, code, "change")
    if verify_password(new, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The new password must be different from the current one")
    user.password_hash = hash_password(new)
    _revoke_all(db, user)
    db.commit()


def _uuid(value):
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def logout(db: Session, token: str, user: User) -> None:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(token)))
    if row is not None and row.user_id == user.id:
        row.revoked = True
        db.commit()
