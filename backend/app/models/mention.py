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
    extend_existing=True,
)


class SocialPlatform(Base):
    __tablename__ = "social_platforms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    mentions: Mapped[list["Mention"]] = relationship("Mention", back_populates="platform")


class InstagramAccount(Base):
    __tablename__ = "instagram_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FacebookAccount(Base):
    """
    Cuenta de Facebook del pool (cookies de sesión).
    Se gestiona desde Plataformas y la lee el worker residencial directamente
    desde la DB de Oracle. El scraper rota entre cuentas por last_used.
    """
    __tablename__ = "facebook_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(150), nullable=False)
    cookies_json: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
    urgency_score: Mapped[float] = mapped_column(Numeric(5, 1), default=0)
    topic_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    topic_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    # ID del hilo/conversación en Twitter (permite agrupar tweets del mismo thread)
    conversation_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    # v2 módulo 6.2: deduplicación inteligente por coseno de embeddings
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    # módulo 7: reconocimiento visual
    media_urls: Mapped[str | None] = mapped_column(Text, nullable=True)           # JSON array de URLs
    visual_match: Mapped[bool | None] = mapped_column(Boolean, nullable=True)     # NULL=sin analizar
    visual_match_names: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON array de nombres
    # módulo 8: búsqueda inversa de imágenes
    image_phash: Mapped[str | None] = mapped_column(String(64), nullable=True)    # pHash hex de primera imagen
    # v2 módulo 6.1: embedding semántico 384 dims (pgvector)
    embedding: Mapped[None] = mapped_column(
        __import__("pgvector.sqlalchemy", fromlist=["Vector"]).Vector(384),
        nullable=True,
    )

    entity: Mapped["Entity"] = relationship("Entity", back_populates="mentions")
    platform: Mapped["SocialPlatform"] = relationship("SocialPlatform", back_populates="mentions")
    keywords: Mapped[list["Keyword"]] = relationship("Keyword", secondary=mention_keywords)

    __table_args__ = (
        __import__("sqlalchemy", fromlist=["UniqueConstraint"]).UniqueConstraint(
            "platform_id", "external_id", name="uq_platform_external_id"
        ),
    )
