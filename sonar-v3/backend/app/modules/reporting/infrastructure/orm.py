from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base
from app.modules.reporting.domain.report import Report


class ReportORM(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    report_type: Mapped[str] = mapped_column(
        Enum("entity", "country", "bots", "alerts", "campaign", name="report_type"),
        nullable=False,
    )
    entity_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("entities.id"), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), ForeignKey("countries.code"), nullable=True)
    date_from: Mapped[str] = mapped_column(Date, nullable=False)
    date_to: Mapped[str] = mapped_column(Date, nullable=False)
    parameters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_domain(self) -> Report:
        return Report(
            id=self.id, name=self.name, report_type=self.report_type,
            entity_id=self.entity_id, country_code=self.country_code,
            date_from=self.date_from, date_to=self.date_to,
            parameters=self.parameters, file_path=self.file_path,
            created_by=self.created_by, created_at=self.created_at,
        )
