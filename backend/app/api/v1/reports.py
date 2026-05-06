import uuid
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.api.audit_utils import log_action
from app.api.deps import get_current_user
from app.database import SessionLocal, get_db
from app.models.entity import Entity
from app.models.report import Report
from app.models.user import User

router = APIRouter(prefix="/reports", tags=["Reportes"])

VALID_TYPES = {"entity", "country", "bots", "alerts", "campaign"}


# ── Schema ────────────────────────────────────────────────────

class ReportCreate(BaseModel):
    name:         str
    report_type:  str
    entity_id:    Optional[uuid.UUID] = None
    country_code: Optional[str]       = None
    date_from:    date
    date_to:      date

    @field_validator("country_code", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        return v if v else None


# ── Helper ────────────────────────────────────────────────────

def _report_dict(r: Report, db: Session) -> dict:
    creator = db.query(User).filter(User.id == r.created_by).first()
    entity  = db.query(Entity).filter(Entity.id == r.entity_id).first() if r.entity_id else None
    return {
        "id":              str(r.id),
        "name":            r.name,
        "report_type":     r.report_type,
        "entity_id":       str(r.entity_id) if r.entity_id else None,
        "entity_name":     entity.name if entity else None,
        "country_code":    r.country_code,
        "date_from":       r.date_from.isoformat(),
        "date_to":         r.date_to.isoformat(),
        "file_path":       r.file_path,
        "created_by_name": creator.full_name if creator else "—",
        "created_at":      r.created_at.isoformat(),
    }


# ── Generador de PDF ──────────────────────────────────────────

def _generate_pdf_task(report_id: str):
    """Tarea en background que genera el PDF y actualiza file_path en BD."""
    from app.reports.generator import generate_report
    db = SessionLocal()
    try:
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            return
        file_path = generate_report(report, db)
        report.file_path = file_path
        db.commit()
    finally:
        db.close()


# ── Endpoints ─────────────────────────────────────────────────

@router.get("")
def list_reports(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    reports = db.query(Report).order_by(Report.created_at.desc()).all()
    return [_report_dict(r, db) for r in reports]


@router.post("", status_code=201)
def create_report(
    request: Request,
    data: ReportCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.report_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail="Tipo de reporte inválido")

    if data.date_from > data.date_to:
        raise HTTPException(status_code=400, detail="date_from debe ser anterior a date_to")

    report = Report(
        name=data.name,
        report_type=data.report_type,
        entity_id=data.entity_id,
        country_code=data.country_code,
        date_from=data.date_from,
        date_to=data.date_to,
        created_by=current_user.id,
    )
    db.add(report)
    db.flush()
    log_action(db, current_user.id, "report_generated", request, "reports", report.id,
               {"name": data.name, "type": data.report_type})
    db.commit()
    db.refresh(report)

    # Generar PDF en background para no bloquear la respuesta
    background_tasks.add_task(_generate_pdf_task, str(report.id))

    return _report_dict(report, db)


@router.get("/{report_id}/download")
def download_report(
    request: Request,
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    if not report.file_path or not Path(report.file_path).exists():
        raise HTTPException(status_code=404, detail="El archivo PDF aún no está listo o fue eliminado")

    log_action(db, current_user.id, "report_downloaded", request, "reports", report.id,
               {"name": report.name})
    db.commit()

    return FileResponse(
        path=report.file_path,
        media_type="application/pdf",
        filename=f"{report.name}.pdf",
    )
