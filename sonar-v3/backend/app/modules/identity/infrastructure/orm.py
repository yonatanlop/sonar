from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base
from app.modules.identity.domain.user import User
from app.shared.types import UserRole


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=UserRole.viewer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_domain(self) -> User:
        return User(
            id=self.id,
            username=self.username,
            email=self.email,
            full_name=self.full_name,
            role=UserRole(self.role),
            active=self.active,
            hashed_password=self.hashed_password,
            telegram_chat_id=self.telegram_chat_id,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @staticmethod
    def from_domain(user: User) -> "UserORM":
        return UserORM(
            id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value if isinstance(user.role, UserRole) else user.role,
            active=user.active,
            hashed_password=user.hashed_password,
            telegram_chat_id=user.telegram_chat_id,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
