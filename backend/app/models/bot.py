import uuid
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AccountProfile(Base):
    __tablename__ = "account_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_id: Mapped[int] = mapped_column(Integer, ForeignKey("social_platforms.id"), nullable=False)
    username: Mapped[str] = mapped_column(String(150), nullable=False)
    external_user_id: Mapped[str | None] = mapped_column(String(150))
    display_name: Mapped[str | None] = mapped_column(String(200))
    account_created: Mapped[datetime | None] = mapped_column(Date)
    followers_count: Mapped[int | None] = mapped_column(Integer)
    following_count: Mapped[int | None] = mapped_column(Integer)
    post_count: Mapped[int | None] = mapped_column(Integer)
    has_profile_photo: Mapped[bool | None] = mapped_column(Boolean)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    bio: Mapped[str | None] = mapped_column(Text)
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    bot_analyses: Mapped[list["BotAnalysis"]] = relationship("BotAnalysis", back_populates="account",
                                                               cascade="all, delete-orphan")

    __table_args__ = (
        __import__("sqlalchemy", fromlist=["UniqueConstraint"]).UniqueConstraint(
            "platform_id", "external_user_id", name="uq_platform_user"
        ),
    )


class BotAnalysis(Base):
    __tablename__ = "bot_analysis"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                                            ForeignKey("account_profiles.id"), nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    bot_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)  # 0.000 a 1.000
    classification: Mapped[str] = mapped_column(
        Enum("real", "anonymous", "bot", "suspicious", name="bot_classification"), nullable=False
    )
    indicators: Mapped[dict | None] = mapped_column(JSONB)
    analyzed_by: Mapped[str] = mapped_column(String(50), default="auto")

    account: Mapped["AccountProfile"] = relationship("AccountProfile", back_populates="bot_analyses")
