import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.api.audit_utils import log_action
from app.api.deps import get_current_user, require_analyst
from app.database import get_db
from app.models.legal_escalation import LegalEscalation
from app.models.mention import Mention
from app.models.user import User

router = APIRouter(prefix="/legal", tags=["Legal"])

VALID_TARGETS = {"iglesia", "mira"}
PAGE_SIZE = 20


class EscalateBody(BaseModel):
    mention_id: uuid.UUID
    target: str
    notes: Optional[str] = None


def _esc_dict(esc: LegalEscalation) -> dict:
    return {
        "id": str(esc.id),
        "mention_id": str(esc.mention_id) if esc.mention_id else None,
        "target": esc.target,
        "snapshot": esc.snapshot_json or {},
        "escalated_by": {
            "id": str(esc.escalated_by),
            "full_name": esc.escalated_by_user.full_name if esc.escalated_by_user else None,
            "username": esc.escalated_by_user.username if esc.escalated_by_user else None,
        },
        "escalated_at": esc.escalated_at.isoformat() if esc.escalated_at else None,
        "received_by": {
            "id": str(esc.received_by),
            "full_name": esc.received_by_user.full_name if esc.received_by_user else None,
            "username": esc.received_by_user.username if esc.received_by_user else None,
        } if esc.received_by else None,
        "received_at": esc.received_at.isoformat() if esc.received_at else None,
        "notes": esc.notes,
    }


@router.post("/escalations", status_code=201)
def create_escalation(
    body: EscalateBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analyst),
):
    if body.target not in VALID_TARGETS:
        raise HTTPException(400, f"target debe ser uno de: {', '.join(VALID_TARGETS)}")

    mention = (
        db.query(Mention)
        .options(joinedload(Mention.platform))
        .filter(Mention.id == body.mention_id)
        .first()
    )
    if not mention:
        raise HTTPException(404, "Mención no encontrada")

    snapshot = {
        "content": mention.content,
        "url": mention.url,
        "author_username": mention.author_username,
        "platform_code": mention.platform.code if mention.platform else None,
        "published_at": mention.published_at.isoformat() if mention.published_at else None,
        "sentiment_label": mention.sentiment_label,
        "urgency_score": float(mention.urgency_score) if mention.urgency_score is not None else None,
        "is_hate_speech": mention.is_hate_speech,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }

    esc = LegalEscalation(
        mention_id=body.mention_id,
        target=body.target,
        snapshot_json=snapshot,
        escalated_by=current_user.id,
        notes=body.notes,
    )
    db.add(esc)
    db.flush()
    log_action(db, current_user.id, "legal_escalation_created", request,
               "legal_escalations", esc.id,
               {"target": body.target, "mention_id": str(body.mention_id)})
    db.commit()

    esc = (
        db.query(LegalEscalation)
        .options(
            joinedload(LegalEscalation.escalated_by_user),
            joinedload(LegalEscalation.received_by_user),
        )
        .filter(LegalEscalation.id == esc.id)
        .first()
    )
    return _esc_dict(esc)


@router.get("/escalations")
def list_escalations(
    target: Optional[str] = Query(None),
    pending: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(LegalEscalation).options(
        joinedload(LegalEscalation.escalated_by_user),
        joinedload(LegalEscalation.received_by_user),
    )
    if target and target in VALID_TARGETS:
        q = q.filter(LegalEscalation.target == target)
    if pending is True:
        q = q.filter(LegalEscalation.received_at.is_(None))
    elif pending is False:
        q = q.filter(LegalEscalation.received_at.isnot(None))

    total = q.count()
    items = (
        q.order_by(LegalEscalation.escalated_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .all()
    )
    return {
        "items": [_esc_dict(e) for e in items],
        "total": total,
        "page": page,
        "pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
    }


@router.patch("/escalations/{esc_id}/receive")
def receive_escalation(
    esc_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    esc = db.query(LegalEscalation).filter(LegalEscalation.id == esc_id).first()
    if not esc:
        raise HTTPException(404, "Escalamiento no encontrado")
    if esc.received_at:
        raise HTTPException(409, "Este escalamiento ya fue marcado como recibido")

    esc.received_by = current_user.id
    esc.received_at = datetime.now(timezone.utc)
    log_action(db, current_user.id, "legal_escalation_received", request,
               "legal_escalations", esc.id, {"target": esc.target})
    db.commit()

    esc = (
        db.query(LegalEscalation)
        .options(
            joinedload(LegalEscalation.escalated_by_user),
            joinedload(LegalEscalation.received_by_user),
        )
        .filter(LegalEscalation.id == esc.id)
        .first()
    )
    return _esc_dict(esc)
