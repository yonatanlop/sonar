"""
Seguimiento a caso — CRUD de casos y sus registros.

Un caso agrupa múltiples publicaciones monitoreadas ("registros") bajo un mismo
nombre (ej. "Caso Payita") con una imagen opcional. Cada registro replica la
matriz de seguimiento del cliente: datos de la publicación, del perfil autor,
indicadores de análisis y el estado de la denuncia.

Acceso: rol de administrador (extensible vía CASE_MANAGER_ROLES en deps.py).
"""
import re
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.audit_utils import log_action
from app.api.deps import require_case_manager
from app.database import get_db
from app.models.case import Case, CaseRecord
from app.models.user import User

router = APIRouter(prefix="/cases", tags=["Seguimiento a caso"])

# Catálogos de valores admitidos (los campos son opcionales, pero si vienen
# deben pertenecer al catálogo). media_type y affects son texto libre.
CASE_MEDIUMS   = ("X", "Facebook", "Instagram", "TikTok", "YouTube", "Threads", "Sitio Web")
CASE_SENTIMENTS = ("Positivo", "Negativo", "Neutral")
CASE_FLAGS      = ("Rojo", "Amarillo", "Verde")

# Tope del data-URI de la imagen (~5 MB de binario ≈ 7M chars de base64)
_MAX_IMAGE_CHARS = 7_000_000
_DATA_URI_RE = re.compile(r"^data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+$")


# ── Schemas ───────────────────────────────────────────────────

class CaseCreate(BaseModel):
    name: str
    image: Optional[str] = None                 # data-URI base64 o None


class CaseUpdate(BaseModel):
    name: Optional[str] = None
    image: Optional[str] = None                 # "" = quitar imagen, None = sin cambio


class RecordBase(BaseModel):
    # Identificación
    affects:   Optional[str] = None
    sentiment: Optional[str] = None
    # Publicación
    publication_url:  Optional[str] = None
    content_text:     Optional[str] = None
    image:            Optional[str] = None       # captura de imagen (data-URI) — "" quita, None sin cambio
    publication_date: Optional[datetime] = None
    medium:           Optional[str] = None
    media_type:       Optional[str] = None
    likes:            Optional[int] = None
    shares:           Optional[int] = None
    comments_count:   Optional[int] = None
    # Perfil autor
    author:             Optional[str] = None
    user_id:            Optional[str] = None
    account_age_months: Optional[str] = None
    followers:          Optional[int] = None
    following:          Optional[int] = None
    verified:           Optional[bool] = None
    bio:                Optional[str] = None
    city:               Optional[str] = None
    # Análisis
    inauthenticity_flag:  Optional[str] = None
    organic_criticism:    Optional[bool] = None
    opposition_criticism: Optional[bool] = None
    coordinated_attack:   Optional[bool] = None
    # Denuncia
    reporter_name: Optional[str] = None
    reported:      Optional[bool] = None
    report_detail: Optional[str] = None
    post_removed:  Optional[bool] = None


class RecordCreate(RecordBase):
    pass


class RecordUpdate(RecordBase):
    pass


# ── Helpers ───────────────────────────────────────────────────

def _validate_choice(value: Optional[str], allowed: tuple, label: str) -> Optional[str]:
    if not value:
        return None
    v = value.strip()
    if v not in allowed:
        raise HTTPException(status_code=422, detail=f"{label} inválido. Opciones: {', '.join(allowed)}")
    return v


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


def _clean_str(v: Optional[str]) -> Optional[str]:
    return (v or "").strip() or None if isinstance(v, str) else v


def _record_dict(r: CaseRecord) -> dict:
    return {
        "id":       str(r.id),
        "case_id":  str(r.case_id),
        "post_id":  r.post_id,
        "affects":  r.affects,
        "sentiment": r.sentiment,
        "publication_url":  r.publication_url,
        "content_text":     r.content_text,
        "has_image":        bool(r.image_data),
        "publication_date": r.publication_date.isoformat() if r.publication_date else None,
        "medium":           r.medium,
        "media_type":       r.media_type,
        "likes":            r.likes,
        "shares":           r.shares,
        "comments_count":   r.comments_count,
        "author":             r.author,
        "user_id":            r.user_id,
        "account_age_months": r.account_age_months,
        "followers":          r.followers,
        "following":          r.following,
        "verified":           r.verified,
        "bio":                r.bio,
        "city":               r.city,
        "inauthenticity_flag":  r.inauthenticity_flag,
        "organic_criticism":    r.organic_criticism,
        "opposition_criticism": r.opposition_criticism,
        "coordinated_attack":   r.coordinated_attack,
        "reporter_name": r.reporter_name,
        "reported":      r.reported,
        "report_detail": r.report_detail,
        "post_removed":  r.post_removed,
        "created_by":    str(r.created_by),
        "created_at":    r.created_at.isoformat() if r.created_at else None,
        "updated_at":    r.updated_at.isoformat() if r.updated_at else None,
    }


def _record_detail_dict(r: CaseRecord) -> dict:
    """Incluye la imagen completa (para editar/previsualizar)."""
    return {**_record_dict(r), "image": r.image_data}


def _case_dict(c: Case) -> dict:
    """Versión liviana para la lista (sin imagen ni registros completos)."""
    records = c.records or []
    resolved = sum(1 for r in records if r.post_removed is True)
    return {
        "id":              str(c.id),
        "name":            c.name,
        "has_image":       bool(c.image_data),
        "record_count":    len(records),
        "resolved_count":  resolved,   # publicaciones eliminadas
        "created_by":      str(c.created_by),
        "created_by_name": c.creator.full_name if c.creator else None,
        "created_at":      c.created_at.isoformat() if c.created_at else None,
        "updated_at":      c.updated_at.isoformat() if c.updated_at else None,
    }


def _case_detail_dict(c: Case) -> dict:
    """Versión completa: imagen del caso + registros livianos (sin bytes de imagen)."""
    records = sorted(c.records or [], key=lambda r: (r.post_id or 0, r.created_at or datetime.min))
    return {
        **_case_dict(c),
        "image":   c.image_data,
        "records": [_record_dict(r) for r in records],
    }


def _get_case_or_404(db: Session, case_id: uuid.UUID) -> Case:
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    return c


def _get_record_or_404(db: Session, case_id: uuid.UUID, record_id: uuid.UUID) -> CaseRecord:
    r = (
        db.query(CaseRecord)
        .filter(CaseRecord.id == record_id, CaseRecord.case_id == case_id)
        .first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return r


# Campos de texto que solo se limpian (trim → None)
_TEXT_FIELDS = (
    "affects", "publication_url", "content_text", "media_type",
    "author", "user_id", "account_age_months", "bio", "city",
    "reporter_name", "report_detail",
)
# Campos que se copian tal cual (numéricos, booleanos, fechas)
_PASSTHROUGH_FIELDS = (
    "publication_date", "likes", "shares", "comments_count",
    "followers", "following", "verified",
    "organic_criticism", "opposition_criticism", "coordinated_attack",
    "reported", "post_removed",
)


def _apply_record_fields(r: CaseRecord, fields: dict) -> None:
    """Aplica los campos presentes de un dict (model_dump exclude_unset) sobre r."""
    for f in _TEXT_FIELDS:
        if f in fields:
            setattr(r, f, _clean_str(fields[f]))
    for f in _PASSTHROUGH_FIELDS:
        if f in fields:
            setattr(r, f, fields[f])
    if "sentiment" in fields:
        r.sentiment = _validate_choice(fields["sentiment"], CASE_SENTIMENTS, "Sentimiento")
    if "medium" in fields:
        r.medium = _validate_choice(fields["medium"], CASE_MEDIUMS, "Medio")
    if "inauthenticity_flag" in fields:
        r.inauthenticity_flag = _validate_choice(fields["inauthenticity_flag"], CASE_FLAGS, "Semáforo")
    if "image" in fields:                        # "" limpia, valor nuevo reemplaza
        r.image_data = _validate_image(fields["image"])


# ── Endpoints: casos ──────────────────────────────────────────

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
    return _case_detail_dict(_get_case_or_404(db, case_id))


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

    c = Case(name=name, image_data=_validate_image(data.image), created_by=user.id)
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
    c = _get_case_or_404(db, case_id)
    fields = data.model_dump(exclude_unset=True)

    if "name" in fields and fields["name"] is not None:
        new_name = fields["name"].strip()
        if not new_name:
            raise HTTPException(status_code=422, detail="El nombre del caso no puede quedar vacío")
        c.name = new_name
    if "image" in fields:                       # "" limpia, valor nuevo reemplaza
        c.image_data = _validate_image(fields["image"])

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
    c = _get_case_or_404(db, case_id)
    log_action(db, user.id, "case_deleted", request, "cases", c.id, {"name": c.name})
    db.delete(c)                                 # cascade borra los registros hijos
    db.commit()


# ── Endpoints: registros de un caso ───────────────────────────

@router.get("/{case_id}/records/{record_id}")
def get_record(
    case_id: uuid.UUID,
    record_id: uuid.UUID,
    db: Session = Depends(get_db),
    _:  User    = Depends(require_case_manager),
):
    return _record_detail_dict(_get_record_or_404(db, case_id, record_id))


@router.post("/{case_id}/records", status_code=status.HTTP_201_CREATED)
def create_record(
    request: Request,
    case_id: uuid.UUID,
    data: RecordCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(require_case_manager),
):
    c = _get_case_or_404(db, case_id)
    next_post_id = (db.query(func.max(CaseRecord.post_id)).scalar() or 0) + 1  # consecutivo global
    r = CaseRecord(case_id=c.id, created_by=user.id, post_id=next_post_id)
    _apply_record_fields(r, data.model_dump(exclude_unset=True))
    db.add(r)
    db.flush()
    log_action(db, user.id, "case_record_created", request, "case_records", r.id, {"case": c.name})
    db.commit()
    db.refresh(r)
    return _record_detail_dict(r)


@router.put("/{case_id}/records/{record_id}")
def update_record(
    request: Request,
    case_id: uuid.UUID,
    record_id: uuid.UUID,
    data: RecordUpdate,
    db:   Session = Depends(get_db),
    user: User    = Depends(require_case_manager),
):
    r = _get_record_or_404(db, case_id, record_id)
    _apply_record_fields(r, data.model_dump(exclude_unset=True))
    log_action(db, user.id, "case_record_updated", request, "case_records", r.id, None)
    db.commit()
    db.refresh(r)
    return _record_detail_dict(r)


@router.delete("/{case_id}/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(
    request: Request,
    case_id: uuid.UUID,
    record_id: uuid.UUID,
    db:   Session = Depends(get_db),
    user: User    = Depends(require_case_manager),
):
    r = _get_record_or_404(db, case_id, record_id)
    log_action(db, user.id, "case_record_deleted", request, "case_records", r.id, None)
    db.delete(r)
    db.commit()
