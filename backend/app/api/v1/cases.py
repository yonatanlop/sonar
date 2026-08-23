"""
Seguimiento a caso — CRUD de casos denunciados.

Cada caso registra una publicación (fecha, URL, plataforma), la descripción de
lo que se hizo en la denuncia, el resultado y la fecha de ejecución del
resultado, con una imagen opcional.

Acceso: rol de administrador (extensible vía CASE_MANAGER_ROLES en deps.py).
"""
import re
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.audit_utils import log_action
from app.api.deps import require_case_manager
from app.database import get_db
from app.models.case import Case
from app.models.user import User

router = APIRouter(prefix="/cases", tags=["Seguimiento a caso"])

# Plataformas admitidas donde se encontró la publicación
CASE_PLATFORMS = ("X", "Facebook", "YouTube", "TikTok", "Instagram")

# Tope del data-URI de la imagen (~5 MB de binario ≈ 7M chars de base64)
_MAX_IMAGE_CHARS = 7_000_000
_DATA_URI_RE = re.compile(r"^data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+$")


# ── Schemas ───────────────────────────────────────────────────

class CaseCreate(BaseModel):
    name: str
    image: Optional[str] = None                 # data-URI base64 o None
    publication_date: Optional[datetime] = None
    publication_url:  Optional[str] = None
    platform:         Optional[str] = None
    action_description: Optional[str] = None
    result:             Optional[str] = None
    result_date:        Optional[datetime] = None


class CaseUpdate(BaseModel):
    name: Optional[str] = None
    image: Optional[str] = None                 # "" = quitar imagen, None = sin cambio
    publication_date: Optional[datetime] = None
    publication_url:  Optional[str] = None
    platform:         Optional[str] = None
    action_description: Optional[str] = None
    result:             Optional[str] = None
    result_date:        Optional[datetime] = None


# ── Helpers ───────────────────────────────────────────────────

def _validate_platform(platform: Optional[str]) -> Optional[str]:
    if not platform:
        return None
    p = platform.strip()
    if p not in CASE_PLATFORMS:
        raise HTTPException(
            status_code=422,
            detail=f"Plataforma inválida. Opciones: {', '.join(CASE_PLATFORMS)}",
        )
    return p


def _validate_image(image: Optional[str]) -> Optional[str]:
    """Valida un data-URI de imagen. Devuelve el string limpio o None si vacío."""
    if not image:
        return None
    img = image.strip()
    if len(img) > _MAX_IMAGE_CHARS:
        raise HTTPException(status_code=422, detail="La imagen supera el tamaño máximo (~5 MB)")
    if not _DATA_URI_RE.match(img):
        raise HTTPException(
            status_code=422,
            detail="Imagen inválida: debe ser un data-URI base64 (data:image/...;base64,...)",
        )
    return img


def _case_dict(c: Case) -> dict:
    """Versión liviana para la lista (sin los bytes de la imagen)."""
    return {
        "id":                 str(c.id),
        "name":               c.name,
        "has_image":          bool(c.image_data),
        "publication_date":   c.publication_date.isoformat() if c.publication_date else None,
        "publication_url":    c.publication_url,
        "platform":           c.platform,
        "action_description": c.action_description,
        "result":             c.result,
        "result_date":        c.result_date.isoformat() if c.result_date else None,
        "created_by":         str(c.created_by),
        "created_by_name":    c.creator.full_name if c.creator else None,
        "created_at":         c.created_at.isoformat() if c.created_at else None,
        "updated_at":         c.updated_at.isoformat() if c.updated_at else None,
    }


def _case_detail_dict(c: Case) -> dict:
    """Versión completa (incluye la imagen) para el detalle/edición."""
    return {**_case_dict(c), "image": c.image_data}


# ── Endpoints ─────────────────────────────────────────────────

@router.get("")
def list_cases(
    db: Session = Depends(get_db),
    _:  User    = Depends(require_case_manager),
):
    cases = db.query(Case).order_by(Case.created_at.desc()).all()
    return [_case_dict(c) for c in cases]


@router.get("/{case_id}")
def get_case(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    _:  User    = Depends(require_case_manager),
):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    return _case_detail_dict(c)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_case(
    request: Request,
    data: CaseCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(require_case_manager),
):
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="El nombre del caso es obligatorio")

    c = Case(
        name=name,
        image_data=_validate_image(data.image),
        publication_date=data.publication_date,
        publication_url=(data.publication_url or "").strip() or None,
        platform=_validate_platform(data.platform),
        action_description=(data.action_description or "").strip() or None,
        result=(data.result or "").strip() or None,
        result_date=data.result_date,
        created_by=user.id,
    )
    db.add(c)
    db.flush()
    log_action(db, user.id, "case_created", request, "cases", c.id, {"name": c.name})
    db.commit()
    db.refresh(c)
    return _case_detail_dict(c)


@router.put("/{case_id}")
def update_case(
    request: Request,
    case_id: uuid.UUID,
    data: CaseUpdate,
    db:   Session = Depends(get_db),
    user: User    = Depends(require_case_manager),
):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    fields = data.model_dump(exclude_unset=True)

    if "name" in fields and fields["name"] is not None:
        new_name = fields["name"].strip()
        if not new_name:
            raise HTTPException(status_code=422, detail="El nombre del caso no puede quedar vacío")
        c.name = new_name
    if "image" in fields:                       # "" limpia, valor nuevo reemplaza
        c.image_data = _validate_image(fields["image"])
    if "publication_date" in fields:
        c.publication_date = fields["publication_date"]
    if "publication_url" in fields:
        c.publication_url = (fields["publication_url"] or "").strip() or None
    if "platform" in fields:
        c.platform = _validate_platform(fields["platform"])
    if "action_description" in fields:
        c.action_description = (fields["action_description"] or "").strip() or None
    if "result" in fields:
        c.result = (fields["result"] or "").strip() or None
    if "result_date" in fields:
        c.result_date = fields["result_date"]

    log_action(db, user.id, "case_updated", request, "cases", c.id, {"name": c.name})
    db.commit()
    db.refresh(c)
    return _case_detail_dict(c)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    request: Request,
    case_id: uuid.UUID,
    db:   Session = Depends(get_db),
    user: User    = Depends(require_case_manager),
):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    log_action(db, user.id, "case_deleted", request, "cases", c.id, {"name": c.name})
    db.delete(c)
    db.commit()
