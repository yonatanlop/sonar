import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LegalEscalation(Base):
    __tablename__ = "legal_escalations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mention_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mentions.id", ondelete="SET NULL"), nullable=True
    )
    target: Mapped[str] = mapped_column(String(20), nullable=False)  # 'iglesia' | 'mira'
    snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    escalated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    escalated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    received_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    escalated_by_user: Mapped["User"] = relationship("User", foreign_keys=[escalated_by])
    received_by_user: Mapped["User | None"] = relationship("User", foreign_keys=[received_by])
