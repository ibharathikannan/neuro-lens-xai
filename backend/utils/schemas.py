import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


def check_password_strength(value: str) -> str:
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("Password must contain at least one letter and one number")
    return value


class UserCreate(BaseModel):
    """Body of POST /api/auth/register"""
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Full name must have at least 2 characters")
        return value

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return check_password_strength(value)


class AdminUserCreate(UserCreate):
    """Body of POST /api/auth/users (administrators add team members)"""
    role: Literal["admin", "clinician"] = "clinician"


class UserUpdate(BaseModel):
    """Body of PATCH /api/auth/users/{id}"""
    role: Optional[Literal["admin", "clinician"]] = None
    is_active: Optional[bool] = None


class PasswordChange(BaseModel):
    """Body of POST /api/auth/change-password"""
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return check_password_strength(value)


class UserLogin(BaseModel):
    """Body of POST /api/auth/login"""
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    """User details returned to the frontend (never includes the password hash)"""
    id: str
    full_name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int          # seconds
    user: UserOut
