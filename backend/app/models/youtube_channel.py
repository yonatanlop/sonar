from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class YoutubeChannel(Base):
    """Canal de YouTube asignado para monitoreo via YouTube Explorer."""
    __tablename__ = "youtube_channels"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    handle        = Column(String(100), unique=True, nullable=False)   # jdoviedoar (sin @)
    channel_id    = Column(String(50),  unique=True, nullable=False)   # UCxxxxx
    channel_name  = Column(String(200), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    active        = Column(Boolean, default=True, nullable=False)
    is_rizoma     = Column(Boolean, default=False, nullable=False)
    entity_id     = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True)
    created_by    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    keywords = relationship(
        "YoutubeChannelKeyword",
        back_populates="channel",
        cascade="all, delete-orphan",
        lazy="select",
    )


class YoutubeChannelKeyword(Base):
    """Palabra clave asignada a un canal de YouTube para búsqueda interna."""
    __tablename__ = "youtube_channel_keywords"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(Integer, ForeignKey("youtube_channels.id", ondelete="CASCADE"), nullable=False)
    keyword    = Column(String(200), nullable=False)
    active     = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    channel = relationship("YoutubeChannel", back_populates="keywords")
