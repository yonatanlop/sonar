import uuid
from datetime import datetime

from sqlalchemy import (Boolean, DateTime, Enum, ForeignKey, Integer,
                        Numeric, String, Table, Text, Column, func)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Tabla de asociación: mención ↔ keywords que la dispararon
mention_keywords = Table(
    "mention_keywords",
    Base.metadata,
    Column("mention_id", UUID(as_uuid=True), ForeignKey("mentions.id"), primary_key=True),
    Column("keyword_id", UUID(as_uuid=True), ForeignKey("keywords.id"), primary_key=True),
)


class SocialPlatform(Base):
    __tablename__ = "social_platforms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    mentions: Mapped[list["Mention"]] = relationship("Mention", back_populates="platform")


class Mention(Base):
    __tablename__ = "mentions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    platform_id: Mapped[int] = mapped_column(Integer, ForeignKey("social_platforms.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_clean: Mapped[str | None] = mapped_column(Text)
    author_username: Mapped[str | None] = mapped_column(String(150))
    author_ext_id: Mapped[str | None] = mapped_column(String(150))
    url: Mapped[str | None] = mapped_column(String(1000))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    language: Mapped[str | None] = mapped_column(String(2))
    country_code: Mapped[str | None] = mapped_column(String(2), ForeignKey("countries.code"))
    sentiment_score: Mapped[float | None] = mapped_column(Numeric(4, 3))  # -1.000 a 1.000
    sentiment_label: Mapped[str | None] = mapped_column(
        Enum("positive", "neutral", "negative", "very_negative", name="sentiment_label")
    )
    hate_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    is_hate_speech: Mapped[bool] = mapped_column(Boolean, default=False)
    is_relevant: Mapped[bool] = mapped_column(Boolean, default=True)
    reach: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)

    entity: Mapped["Entity"] = relationship("Entity", back_populates="mentions")
    platform: Mapped["SocialPlatform"] = relationship("SocialPlatform", back_populates="mentions")
    keywords: Mapped[list["Keyword"]] = relationship("Keyword", secondary=mention_keywords)

    __table_args__ = (
        __import__("sqlalchemy", fromlist=["UniqueConstraint"]).UniqueConstraint(
            "platform_id", "external_id", name="uq_platform_external_id"
        ),
    )
