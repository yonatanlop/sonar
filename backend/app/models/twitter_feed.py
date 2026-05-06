import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TwitterFeed(Base):
    """
    Registro de un monitor de Twitter Explorer.
    Puede ser un @usuario, #hashtag o palabra clave libre.
    Cada feed tiene una Entity interna auto-creada para que las menciones
    pasen por el pipeline NLP existente (sentimiento, urgencia, embeddings).
    """
    __tablename__ = "twitter_feeds"

    id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feed_type:    Mapped[str]       = mapped_column(String(20),  nullable=False)   # 'user' | 'hashtag' | 'keyword'
    term:         Mapped[str]       = mapped_column(String(200), nullable=False)   # username sin @, hashtag sin #
    display_name: Mapped[str]       = mapped_column(String(200), nullable=False)   # "@pepito", "#MIRA"
    entity_id:    Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True)
    active:       Mapped[bool]      = mapped_column(Boolean, default=True)
    is_rizoma:    Mapped[bool]      = mapped_column(Boolean, default=False, nullable=False)
    created_by:   Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at:   Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())

    entity: Mapped["Entity"] = relationship("Entity", foreign_keys=[entity_id])  # type: ignore
