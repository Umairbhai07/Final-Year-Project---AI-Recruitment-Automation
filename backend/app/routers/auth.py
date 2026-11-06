from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.database import get_db
from app.models import User
from app.schemas.auth import (
    ChangePasswordCodeIn,
    ChangePasswordIn,
    ForgotPasswordIn,
    LoginIn,
    RefreshIn,
    RegisterIn,
    ResetPasswordIn,
    ResetWithCodeIn,
    TokenOut,
    UserOut,
    VerifyEmailIn,
)
from app.services import auth as svc
from app.services.profile import photo_url

router = APIRouter(prefix="/auth", tags=["auth"])


def user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.must_verify = settings.REQUIRE_EMAIL_VERIFICATION and not user.email_verified
    if user.profile is not None:
        out.photo_url = photo_url(user.id, user.profile.photo_key)
    return out


def _client_ip(request: Request) -> str:
    # Behind Render's proxy the real client IP is the LAST X-Forwarded-For entry (added by the proxy);
    # earlier entries can be spoofed by the client, so they are ignored.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def register(request: Request, data: RegisterIn, db: Session = Depends(get_db)):
    return user_out(svc.register(db, data))


@router.post("/login", response_model=TokenOut)
@limiter.limit("30/minute")
def login(request: Request, data: LoginIn, db: Session = Depends(get_db)):
    user, access, refresh = svc.login(db, data, _client_ip(request))
    return TokenOut(access_token=access, refresh_token=refresh, user=user_out(user))


@router.post("/refresh", response_model=TokenOut)
def refresh(data: RefreshIn, db: Session = Depends(get_db)):
    user, access, new_refresh = svc.refresh(db, data.refresh_token)
    return TokenOut(access_token=access, refresh_token=new_refresh, user=user_out(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: RefreshIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.logout(db, data.refresh_token, user)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
def forgot_password(request: Request, data: ForgotPasswordIn, db: Session = Depends(get_db)):
    svc.forgot_password(db, data.email)
    return {"detail": "If an account exists for this email, a code has been sent."}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def reset_password(request: Request, data: ResetPasswordIn, db: Session = Depends(get_db)):
    svc.reset_password(db, data.token, data.password)


@router.post("/reset-password-code", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def reset_password_code(request: Request, data: ResetWithCodeIn, db: Session = Depends(get_db)):
    svc.reset_with_code(db, data.email, data.code, data.password)


@router.post("/change-password/send-code", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
def change_password_code(request: Request, data: ChangePasswordCodeIn, user: User = Depends(get_current_user)):
    svc.send_change_code(user, data.current_password)
    return {"detail": f"A code has been sent to {user.email}."}


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def change_password(
    request: Request, data: ChangePasswordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    svc.change_password(db, user, data.code, data.new_password)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.post("/verify-email", response_model=UserOut)
@limiter.limit("20/minute")
def verify_email(request: Request, data: VerifyEmailIn, db: Session = Depends(get_db)):
    return user_out(svc.verify_email(db, data.token))


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/minute")
def resend_verification(request: Request, user: User = Depends(get_current_user)):
    if not user.email_verified:
        svc.send_verification(user)
    return {"detail": "If your email is not confirmed yet, a new link has been sent."}
