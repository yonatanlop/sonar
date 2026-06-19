"""
Grupos administrar y cerrar — registro de grupos de Facebook a cerrar.
Guarda URL, razón del cierre, fecha de inicio del proceso y fecha fin.
El estado (en proceso / cerrado) se deriva de end_date.
Accesible para analistas y admin.
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.audit_utils import log_action
from app.api.deps import require_analyst
from app.database import get_db
from app.models.facebook_group import FacebookGroup
from app.models.user import User

router = APIRouter(prefix="/facebook-groups", tags=["Grupos a cerrar"])


# ── Schemas ───────────────────────────────────────────────────

class GroupCreate(BaseModel):
    group_url: str
    reason: Optional[str] = None
    start_date: datetime
    end_date: Optional[datetime] = None


class GroupUpdate(BaseModel):
    group_url: Optional[str] = None
    reason: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


# ── Helpers ───────────────────────────────────────────────────

def _group_dict(g: FacebookGroup) -> dict:
    return {
        "id":         str(g.id),
        "group_url":  g.group_url,
        "reason":     g.reason,
        "start_date": g.start_date.isoformat() if g.start_date else None,
        "end_date":   g.end_date.isoformat() if g.end_date else None,
        "status":     "cerrado" if g.end_date else "en_proceso",
        "created_by": str(g.created_by),
        "created_by_name": g.creator.full_name if g.creator else None,
        "created_at": g.created_at.isoformat() if g.created_at else None,
    }


# ── Endpoints ─────────────────────────────────────────────────

@router.get("")
def list_groups(
    db: Session = Depends(get_db),
    _:  User    = Depends(require_analyst),
):
    groups = db.query(FacebookGroup).order_by(FacebookGroup.created_at.desc()).all()
    return [_group_dict(g) for g in groups]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_group(
    request: Request,
    data: GroupCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(require_analyst),
):
    if not data.group_url.strip():
        raise HTTPException(status_code=422, detail="La URL del grupo es obligatoria")

    g = FacebookGroup(
        group_url=data.group_url.strip(),
        reason=(data.reason or None),
        start_date=data.start_date,
        end_date=data.end_date,
        created_by=user.id,
    )
    db.add(g)
    db.flush()
    log_action(db, user.id, "facebook_group_added", request, "facebook_groups", g.id,
               {"group_url": g.group_url})
    db.commit()
    db.refresh(g)
    return _group_dict(g)


@router.put("/{group_id}")
def update_group(
    request: Request,
    group_id: uuid.UUID,
    data: GroupUpdate,
    db:   Session = Depends(get_db),
    user: User    = Depends(require_analyst),
):
    g = db.query(FacebookGroup).filter(FacebookGroup.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")

    fields = data.model_dump(exclude_unset=True)
    if "group_url" in fields and fields["group_url"] is not None:
        g.group_url = fields["group_url"].strip()
    if "reason" in fields:
        g.reason = fields["reason"] or None
    if "start_date" in fields and fields["start_date"] is not None:
        g.start_date = fields["start_date"]
    if "end_date" in fields:
        g.end_date = fields["end_date"]

    log_action(db, user.id, "facebook_group_updated", request, "facebook_groups", g.id,
               {"group_url": g.group_url, "status": "cerrado" if g.end_date else "en_proceso"})
    db.commit()
    db.refresh(g)
    return _group_dict(g)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    request: Request,
    group_id: uuid.UUID,
    db:   Session = Depends(get_db),
    user: User    = Depends(require_analyst),
):
    g = db.query(FacebookGroup).filter(FacebookGroup.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    log_action(db, user.id, "facebook_group_deleted", request, "facebook_groups", g.id,
               {"group_url": g.group_url})
    db.delete(g)
    db.commit()
