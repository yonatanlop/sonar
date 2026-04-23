from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.shared.deps import get_db, get_current_user, require_analyst
from app.shared.exceptions import NotFoundError
from app.modules.legal.application.schemas import (
    LegalCaseCreate, LegalCasePatch, LegalCaseOut, LegalEventCreate,
    LegalEventOut, LegalDocumentOut,
)
from app.modules.legal.domain.legal_case import LegalCase, LegalEvent, LegalDocument
from app.modules.legal.infrastructure.legal_repository import (
    SqlLegalCaseRepository, SqlLegalEventRepository, SqlLegalDocumentRepository
)

router = APIRouter(prefix="/legal", tags=["Legal"])

ESCALATION_MAP = {
    "platform": "mira_legal",
    "mira_legal": "church_legal",
}

UPLOAD_DIR = "storage/legal_docs"


@router.get("/cases", response_model=list[LegalCaseOut])
def list_cases(
    level: str | None = Query(None),
    status: str | None = Query(None),
    entity_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    repo = SqlLegalCaseRepository(db)
    return [_case_out(c, db) for c in repo.list(level=level, status=status, entity_id=entity_id)]


@router.post("/cases", response_model=LegalCaseOut, status_code=201)
def create_case(
    data: LegalCaseCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_analyst),
):
    repo = SqlLegalCaseRepository(db)
    now = datetime.now(timezone.utc)
    case = LegalCase(
        id=uuid4(), mention_id=data.mention_id, entity_id=data.entity_id,
        title=data.title, description=data.description, level=data.level,
        status="open", assigned_to=data.assigned_to,
        created_by=current_user.id, created_at=now, updated_at=now,
    )
    saved = repo.create(case)
    _add_event(db, saved.id, "created", f"Caso creado en nivel {data.level}", None, None, current_user.id)
    return _case_out(saved, db)


@router.get("/cases/{case_id}", response_model=LegalCaseOut)
def get_case(case_id: UUID, db: Session = Depends(get_db), _=Depends(get_current_user)):
    case = SqlLegalCaseRepository(db).get_by_id(case_id)
    if not case:
        raise NotFoundError("Caso no encontrado")
    return _case_out(case, db)


@router.patch("/cases/{case_id}", response_model=LegalCaseOut)
def update_case(
    case_id: UUID,
    data: LegalCasePatch,
    db: Session = Depends(get_db),
    current_user=Depends(require_analyst),
):
    repo = SqlLegalCaseRepository(db)
    case = repo.get_by_id(case_id)
    if not case:
        raise NotFoundError("Caso no encontrado")
    if data.title:
        case.title = data.title
    if data.description:
        case.description = data.description
    if data.status:
        case.status = data.status
    if data.assigned_to is not None:
        case.assigned_to = data.assigned_to
    updated = repo.update(case)
    return _case_out(updated, db)


@router.post("/cases/{case_id}/escalate", response_model=LegalCaseOut)
def escalate_case(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_analyst),
):
    repo = SqlLegalCaseRepository(db)
    case = repo.get_by_id(case_id)
    if not case:
        raise NotFoundError("Caso no encontrado")
    next_level = ESCALATION_MAP.get(case.level)
    if not next_level:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="El caso ya está en el nivel máximo")
    from_level = case.level
    case.level = next_level
    case.status = "escalated"
    updated = repo.update(case)
    _add_event(db, case_id, "escalated",
               f"Escalado de {from_level} a {next_level}",
               from_level, next_level, current_user.id)
    return _case_out(updated, db)


@router.post("/cases/{case_id}/events", response_model=LegalEventOut, status_code=201)
def add_event(
    case_id: UUID,
    data: LegalEventCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_analyst),
):
    if not SqlLegalCaseRepository(db).get_by_id(case_id):
        raise NotFoundError("Caso no encontrado")
    event = _add_event(db, case_id, data.event_type, data.description, None, None, current_user.id)
    return LegalEventOut(
        id=event.id, event_type=event.event_type, description=event.description,
        from_level=event.from_level, to_level=event.to_level,
        created_by=event.created_by, created_at=event.created_at,
    )


@router.post("/cases/{case_id}/documents", response_model=LegalDocumentOut, status_code=201)
async def upload_document(
    case_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_analyst),
):
    if not SqlLegalCaseRepository(db).get_by_id(case_id):
        raise NotFoundError("Caso no encontrado")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid4()}_{file.filename}"
    path = os.path.join(UPLOAD_DIR, filename)
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    doc = LegalDocument(
        id=uuid4(), case_id=case_id, file_name=file.filename,
        file_path=path, file_type=file.content_type or "application/octet-stream",
        uploaded_by=current_user.id, uploaded_at=datetime.now(timezone.utc),
    )
    saved = SqlLegalDocumentRepository(db).create(doc)
    return LegalDocumentOut(id=saved.id, file_name=saved.file_name,
                            file_type=saved.file_type, uploaded_at=saved.uploaded_at)


# ── Helpers ───────────────────────────────────────────────────
def _add_event(db, case_id, event_type, description, from_level, to_level, created_by) -> LegalEvent:
    event = LegalEvent(
        id=uuid4(), case_id=case_id, event_type=event_type,
        description=description, from_level=from_level, to_level=to_level,
        created_by=created_by, created_at=datetime.now(timezone.utc),
    )
    return SqlLegalEventRepository(db).create(event)


def _case_out(case: LegalCase, db: Session) -> LegalCaseOut:
    events = SqlLegalEventRepository(db).list_by_case(case.id)
    docs = SqlLegalDocumentRepository(db).list_by_case(case.id)
    return LegalCaseOut(
        id=case.id, entity_id=case.entity_id, mention_id=case.mention_id,
        title=case.title, description=case.description, level=case.level,
        status=case.status, assigned_to=case.assigned_to,
        created_by=case.created_by, created_at=case.created_at, updated_at=case.updated_at,
        events=[LegalEventOut(id=e.id, event_type=e.event_type, description=e.description,
                               from_level=e.from_level, to_level=e.to_level,
                               created_by=e.created_by, created_at=e.created_at) for e in events],
        documents=[LegalDocumentOut(id=d.id, file_name=d.file_name,
                                     file_type=d.file_type, uploaded_at=d.uploaded_at) for d in docs],
    )
