from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (Boolean, Column, Date, DateTime, Enum, ForeignKey,
                        Integer, Numeric, SmallInteger, String, Table, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database import Base
from app.modules.collection.domain.mention import Mention, AccountProfile, BotAnalysis

try:
    from pgvector.sqlalchemy import Vector
    _vector_type = Vector(384)
except ImportError:
    _vector_type = None

mention_keywords = Table(
    "mention_keywords",
    Base.metadata,
    Column("mention_id", String(36), ForeignKey("mentions.id"), primary_key=True),
    Column("keyword_id", String(36), ForeignKey("keywords.id"), primary_key=True),
)


class MentionORM(Base):
    __tablename__ = "mentions"
    __table_args__ = (
        UniqueConstraint("platform_id", "external_id", name="uq_platform_external_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"), nullable=False)
    platform_id: Mapped[int] = mapped_column(Integer, ForeignKey("social_platforms.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_clean: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_username: Mapped[str | None] = mapped_column(String(150), nullable=True)
    author_ext_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    language: Mapped[str | None] = mapped_column(String(2), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), ForeignKey("countries.code"), nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    sentiment_label: Mapped[str | None] = mapped_column(
        Enum("positive", "neutral", "negative", "very_negative", name="sentiment_label"), nullable=True
    )
    hate_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    is_hate_speech: Mapped[bool] = mapped_column(Boolean, default=False)
    is_relevant: Mapped[bool] = mapped_column(Boolean, default=True)
    reach: Mapped[int] = mapped_column(Integer, default=0)
    urgency_score: Mapped[float] = mapped_column(Numeric(5, 1), default=0)
    topic_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    topic_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    conversation_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    media_urls: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_match: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    visual_match_names: Mapped[str | None] = mapped_column(Text, nullable=True)

    if _vector_type is not None:
        embedding = mapped_column(_vector_type, nullable=True)

    def to_domain(self) -> Mention:
        return Mention(
            id=self.id, entity_id=self.entity_id, platform_id=self.platform_id,
            external_id=self.external_id, content=self.content,
            content_clean=self.content_clean, author_username=self.author_username,
            author_ext_id=self.author_ext_id, url=self.url,
            published_at=self.published_at, collected_at=self.collected_at,
            language=self.language, country_code=self.country_code,
            sentiment_score=float(self.sentiment_score) if self.sentiment_score is not None else None,
            sentiment_label=self.sentiment_label,
            hate_score=float(self.hate_score) if self.hate_score is not None else None,
            is_hate_speech=self.is_hate_speech, is_relevant=self.is_relevant,
            reach=self.reach,
            urgency_score=float(self.urgency_score) if self.urgency_score is not None else 0,
            topic_id=self.topic_id, topic_label=self.topic_label,
            processed=self.processed, conversation_id=self.conversation_id,
            is_duplicate=self.is_duplicate, media_urls=self.media_urls,
            visual_match=self.visual_match, visual_match_names=self.visual_match_names,
        )


class AccountProfileORM(Base):
    __tablename__ = "account_profiles"
    __table_args__ = (
        UniqueConstraint("platform_id", "external_user_id", name="uq_platform_user"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    platform_id: Mapped[int] = mapped_column(Integer, ForeignKey("social_platforms.id"), nullable=False)
    username: Mapped[str] = mapped_column(String(150), nullable=False)
    external_user_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    account_created: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    followers_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    following_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    post_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_profile_photo: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bot_probability: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)

    bot_analyses: Mapped[list["BotAnalysisORM"]] = relationship("BotAnalysisORM", back_populates="account",
                                                                  cascade="all, delete-orphan")

    def to_domain(self) -> AccountProfile:
        return AccountProfile(
            id=self.id, platform_id=self.platform_id, username=self.username,
            external_user_id=self.external_user_id, display_name=self.display_name,
            account_created=self.account_created, followers_count=self.followers_count,
            following_count=self.following_count, post_count=self.post_count,
            has_profile_photo=self.has_profile_photo, verified=self.verified,
            bio=self.bio, location_text=self.location_text,
            last_analyzed_at=self.last_analyzed_at,
            bot_probability=float(self.bot_probability) if self.bot_probability is not None else None,
        )


class BotAnalysisORM(Base):
    __tablename__ = "bot_analysis"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_profile_id: Mapped[str] = mapped_column(String(36),
                                                      ForeignKey("account_profiles.id"), nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    bot_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    classification: Mapped[str] = mapped_column(
        Enum("real", "anonymous", "bot", "suspicious", name="bot_classification"), nullable=False
    )
    indicators: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    analyzed_by: Mapped[str] = mapped_column(String(50), default="auto")

    account: Mapped["AccountProfileORM"] = relationship("AccountProfileORM", back_populates="bot_analyses")

    def to_domain(self) -> BotAnalysis:
        return BotAnalysis(
            id=self.id, account_profile_id=self.account_profile_id,
            analyzed_at=self.analyzed_at, bot_score=float(self.bot_score),
            classification=self.classification, indicators=self.indicators,
            analyzed_by=self.analyzed_by,
        )
