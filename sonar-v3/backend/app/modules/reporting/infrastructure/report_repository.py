from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.reporting.domain.report import Report
from app.modules.reporting.domain.ports import IReportRepository
from app.modules.reporting.infrastructure.orm import ReportORM


class SqlReportRepository(IReportRepository):
    def __init__(self, db: Session):
        self._db = db

    def list(self, created_by: UUID | None = None) -> list[Report]:
        q = self._db.query(ReportORM)
        if created_by:
            q = q.filter(ReportORM.created_by == str(created_by))
        return [r.to_domain() for r in q.order_by(ReportORM.created_at.desc()).all()]

    def get_by_id(self, report_id: UUID) -> Report | None:
        row = self._db.query(ReportORM).filter(ReportORM.id == str(report_id)).first()
        return row.to_domain() if row else None

    def create(self, report: Report) -> Report:
        row = ReportORM(
            id=str(report.id), name=report.name, report_type=report.report_type,
            entity_id=str(report.entity_id) if report.entity_id else None,
            country_code=report.country_code, date_from=report.date_from,
            date_to=report.date_to, parameters=report.parameters,
            file_path=report.file_path, created_by=str(report.created_by),
            created_at=report.created_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def update_path(self, report_id: UUID, file_path: str) -> Report:
        row = self._db.query(ReportORM).filter(ReportORM.id == str(report_id)).first()
        row.file_path = file_path
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def delete(self, report_id: UUID) -> None:
        self._db.query(ReportORM).filter(ReportORM.id == str(report_id)).delete()
        self._db.commit()
