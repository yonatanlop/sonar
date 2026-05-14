from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.database import Base


class YtKeywordHit(Base):
    """Fragmento de video encontrado por Indexor al buscar una keyword."""
    __tablename__ = "yt_keyword_hits"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    hash              = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256(url)
    channel_id        = Column(Integer, ForeignKey("youtube_channels.id", ondelete="CASCADE"), nullable=False, index=True)
    keyword_id        = Column(Integer, ForeignKey("youtube_channel_keywords.id", ondelete="SET NULL"), nullable=True, index=True)
    keyword           = Column(String(200), nullable=False)
    yt_media_video_id = Column(String(50), nullable=False)
    inicio            = Column(String(20), nullable=True)
    texto             = Column(Text, nullable=True)
    url               = Column(String(1000), nullable=False)
    query_date        = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    channel     = relationship("YoutubeChannel", back_populates="keyword_hits")
    keyword_ref = relationship("YoutubeChannelKeyword", back_populates="hits")
