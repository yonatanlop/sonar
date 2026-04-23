from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database import Base
from app.modules.legal.domain.legal_case import LegalCase, LegalEvent, LegalDocument


class LegalCaseORM(Base):
    __tablename__ = "legal_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    mention_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("mentions.id"), nullable=True)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(
        Enum("platform", "mira_legal", "church_legal", name="legal_case_level"),
        nullable=False, default="platform",
    )
    status: Mapped[str] = mapped_column(
        Enum("open", "in_progress", "closed", "escalated", name="legal_case_status"),
        nullable=False, default="open",
    )
    assigned_to: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    events: Mapped[list["LegalEventORM"]] = relationship("LegalEventORM", back_populates="case",
                                                           cascade="all, delete-orphan",
                                                           order_by="LegalEventORM.created_at")
    documents: Mapped[list["LegalDocumentORM"]] = relationship("LegalDocumentORM", back_populates="case",
                                                                cascade="all, delete-orphan")

    def to_domain(self) -> LegalCase:
        return LegalCase(
            id=self.id, mention_id=self.mention_id, entity_id=self.entity_id,
            title=self.title, description=self.description, level=self.level,
            status=self.status, assigned_to=self.assigned_to,
            created_by=self.created_by, created_at=self.created_at, updated_at=self.updated_at,
        )


class LegalEventORM(Base):
    __tablename__ = "legal_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("legal_cases.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    from_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    case: Mapped["LegalCaseORM"] = relationship("LegalCaseORM", back_populates="events")

    def to_domain(self) -> LegalEvent:
        return LegalEvent(
            id=self.id, case_id=self.case_id, event_type=self.event_type,
            description=self.description, from_level=self.from_level,
            to_level=self.to_level, created_by=self.created_by, created_at=self.created_at,
        )


class LegalDocumentORM(Base):
    __tablename__ = "legal_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("legal_cases.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    case: Mapped["LegalCaseORM"] = relationship("LegalCaseORM", back_populates="documents")

    def to_domain(self) -> LegalDocument:
        return LegalDocument(
            id=self.id, case_id=self.case_id, file_name=self.file_name,
            file_path=self.file_path, file_type=self.file_type,
            uploaded_by=self.uploaded_by, uploaded_at=self.uploaded_at,
        )
