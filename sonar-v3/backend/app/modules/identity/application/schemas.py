from __future__ import annotations

from pydantic import BaseModel, EmailStr
from uuid import UUID

from app.shared.types import UserRole


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    password: str
    role: UserRole = UserRole.viewer
    telegram_chat_id: str | None = None


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    role: UserRole | None = None
    active: bool | None = None
    telegram_chat_id: str | None = None
    password: str | None = None


class UserOut(BaseModel):
    id: UUID
    username: str
    email: str
    full_name: str
    role: UserRole
    active: bool
    telegram_chat_id: str | None = None

    model_config = {"from_attributes": True}


class UserMinimal(BaseModel):
    id: UUID
    username: str
    full_name: str
    role: UserRole

    model_config = {"from_attributes": True}


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class PasswordChange(BaseModel):
    current_password: str
    new_password: str
