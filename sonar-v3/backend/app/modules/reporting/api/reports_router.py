from __future__ import annotations

import os
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.shared.deps import get_db, get_current_user, require_analyst
from app.modules.reporting.domain.report import Report
from app.modules.reporting.infrastructure.report_repository import SqlReportRepository
from app.shared.exceptions import NotFoundError

router = APIRouter(prefix="/reports", tags=["Reportes"])


class ReportCreate(BaseModel):
    name: str
    report_type: str
    entity_id: UUID | None = None
    country_code: str | None = None
    date_from: date
    date_to: date
    parameters: dict | None = None


class ReportOut(BaseModel):
    id: UUID
    name: str
    report_type: str
    entity_id: UUID | None = None
    country_code: str | None = None
    date_from: date
    date_to: date
    file_path: str | None = None
    created_at: datetime
    ready: bool = False


@router.get("", response_model=list[ReportOut])
def list_reports(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    repo = SqlReportRepository(db)
    return [_to_out(r) for r in repo.list()]


@router.post("", response_model=ReportOut, status_code=201)
def create_report(
    data: ReportCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(require_analyst),
):
    repo = SqlReportRepository(db)
    report = Report(
        id=uuid4(), name=data.name, report_type=data.report_type,
        entity_id=data.entity_id, country_code=data.country_code,
        date_from=data.date_from, date_to=data.date_to,
        parameters=data.parameters, file_path=None,
        created_by=current_user.id, created_at=datetime.now(timezone.utc),
    )
    saved = repo.create(report)
    background_tasks.add_task(_generate_pdf, saved.id)
    return _to_out(saved)


@router.get("/{report_id}/download")
def download_report(report_id: UUID, db: Session = Depends(get_db), _=Depends(get_current_user)):
    repo = SqlReportRepository(db)
    report = repo.get_by_id(report_id)
    if not report:
        raise NotFoundError("Reporte no encontrado")
    if not report.file_path or not os.path.exists(report.file_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="El PDF aún no está listo")
    return FileResponse(report.file_path, media_type="application/pdf",
                        filename=os.path.basename(report.file_path))


@router.delete("/{report_id}", status_code=204)
def delete_report(report_id: UUID, db: Session = Depends(get_db), _=Depends(require_analyst)):
    repo = SqlReportRepository(db)
    report = repo.get_by_id(report_id)
    if not report:
        raise NotFoundError("Reporte no encontrado")
    if report.file_path and os.path.exists(report.file_path):
        os.remove(report.file_path)
    repo.delete(report_id)


def _generate_pdf(report_id: UUID):
    """Background task — generates PDF via WeasyPrint. Full implementation in tasks/reporting_tasks.py."""
    from app.shared.celery_app import celery_app
    celery_app.send_task("app.tasks.reporting_tasks.generate_report_pdf", args=[str(report_id)])


def _to_out(r: Report) -> ReportOut:
    return ReportOut(
        id=r.id, name=r.name, report_type=r.report_type,
        entity_id=r.entity_id, country_code=r.country_code,
        date_from=r.date_from, date_to=r.date_to,
        file_path=r.file_path, created_at=r.created_at,
        ready=bool(r.file_path and os.path.exists(r.file_path)),
    )
