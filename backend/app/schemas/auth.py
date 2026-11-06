import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import Role


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name is required")
        return v

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    role: Role | None = None  # which portal the user is signing in to (optional)

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()


def _check_password(v: str) -> str:
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one number")
    return v


class ForgotPasswordIn(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=10, max_length=2000)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return _check_password(v)


class ResetWithCodeIn(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\s*\d{6}\s*$")
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return _check_password(v)


class ChangePasswordCodeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)


class ChangePasswordIn(BaseModel):
    code: str = Field(pattern=r"^\s*\d{6}\s*$")
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return _check_password(v)


class VerifyEmailIn(BaseModel):
    token: str = Field(min_length=10, max_length=2000)


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    role: Role
    created_at: datetime
    email_verified: bool = True
    must_verify: bool = False  # verification is switched on and this account has not confirmed its email
    photo_url: str | None = None  # candidates: their profile photo, for the account menu


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
