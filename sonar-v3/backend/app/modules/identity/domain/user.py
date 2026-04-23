from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.shared.types import UserRole


@dataclass
class User:
    id: UUID
    username: str
    email: str
    full_name: str
    role: UserRole
    active: bool
    hashed_password: str
    telegram_chat_id: str | None
    created_at: datetime
    updated_at: datetime
