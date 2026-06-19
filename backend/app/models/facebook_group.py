import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FacebookGroup(Base):
    """
    Registro de un grupo de Facebook que se va a cerrar.
    El estado (en proceso / cerrado) se deriva de end_date.
    """
    __tablename__ = "facebook_groups"

    id:         Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_url:  Mapped[str]            = mapped_column(String(500), nullable=False)
    reason:     Mapped[str | None]     = mapped_column(Text, nullable=True)
    start_date: Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)
    end_date:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821
