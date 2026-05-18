import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TwitterKeywordConfig(Base):
    __tablename__ = "twitter_keyword_config"

    id:              Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    is_active:       Mapped[bool]             = mapped_column(Boolean, default=False, nullable=False)
    activated_at:    Mapped[datetime | None]  = mapped_column(DateTime(timezone=True))
    stopped_at:      Mapped[datetime | None]  = mapped_column(DateTime(timezone=True))
    last_run_at:     Mapped[datetime | None]  = mapped_column(DateTime(timezone=True))
    activated_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class TwitterKeywordTerm(Base):
    __tablename__ = "twitter_keyword_terms"

    id:             Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    term:           Mapped[str]              = mapped_column(String(200), nullable=False)
    term_type:      Mapped[str]              = mapped_column(String(10),  nullable=False)  # 'keyword' | 'hashtag'
    secondary_term: Mapped[str | None]       = mapped_column(String(200), nullable=True)   # término adicional (solo keywords)
    logic_op:       Mapped[str]              = mapped_column(String(3),   nullable=False, default="AND")  # AND | OR | NOT
    is_active:      Mapped[bool]             = mapped_column(Boolean, default=True, nullable=False)
    created_at:     Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by_id:  Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
