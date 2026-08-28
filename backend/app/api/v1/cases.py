"""
Seguimiento a caso — CRUD de casos, cuentas y publicaciones (3 niveles).

Jerarquía: Caso (persona) → Cuenta (perfil por red social) → Publicación.
- El caso guarda nombre + imagen.
- La cuenta guarda el perfil (una vez por red) y su estado (¿eliminada?, ¿creó
  cuenta nueva?).
- La publicación guarda solo lo específico del post (contenido, métricas,
  análisis de inautenticidad y denuncia).

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
from app.models.case import Case, CaseAccount, CaseRecord
from app.models.user import User

router = APIRouter(prefix="/cases", tags=["Seguimiento a caso"])

# Catálogos admitidos (los campos son opcionales; si vienen deben pertenecer).
CASE_MEDIUMS    = ("X", "Facebook", "Instagram", "TikTok", "YouTube", "Threads", "Sitio Web")
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


class AccountBase(BaseModel):
    medium:      Optional[str] = None
    author:      Optional[str] = None
    profile_url: Optional[str] = None
    user_id:     Optional[str] = None
    account_age_months: Optional[str] = None
    followers:   Optional[int] = None
    following:   Optional[int] = None
    verified:    Optional[bool] = None
    bio:         Optional[str] = None
    city:        Optional[str] = None
    account_removed:     Optional[bool] = None
    removed_date:        Optional[datetime] = None
    created_new_account: Optional[bool] = None
    new_account_info:    Optional[str] = None


class AccountCreate(AccountBase):
    pass


class AccountUpdate(AccountBase):
    pass


class RecordBase(BaseModel):
    affects:   Optional[str] = None
    sentiment: Optional[str] = None
    publication_url:  Optional[str] = None
    content_text:     Optional[str] = None
    image:            Optional[str] = None       # captura (data-URI) — "" quita, None sin cambio
    publication_date: Optional[datetime] = None
    media_type:       Optional[str] = None
    likes:            Optional[int] = None
    shares:           Optional[int] = None
    comments_count:   Optional[int] = None
    inauthenticity_flag:  Optional[str] = None
    organic_criticism:    Optional[bool] = None
    opposition_criticism: Optional[bool] = None
    coordinated_attack:   Optional[bool] = None
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
    if not image:
        return None
    img = image.strip()
    if len(img) > _MAX_IMAGE_CHARS:
        raise HTTPException(status_code=422, detail="La imagen supera el tamaño máximo (~5 MB)")
    if not _DATA_URI_RE.match(img):
        raise HTTPException(status_code=422, detail="Imagen inválida: debe ser un data-URI base64")
    return img


def _clean_str(v):
    return (v or "").strip() or None if isinstance(v, str) else v


# ── Serialización ─────────────────────────────────────────────

def _record_dict(r: CaseRecord) -> dict:
    return {
        "id":       str(r.id),
        "account_id": str(r.account_id),
        "case_id":  str(r.case_id),
        "post_id":  r.post_id,
        "affects":  r.affects,
        "sentiment": r.sentiment,
        "publication_url":  r.publication_url,
        "content_text":     r.content_text,
        "has_image":        bool(r.image_data),
        "publication_date": r.publication_date.isoformat() if r.publication_date else None,
        "media_type":       r.media_type,
        "likes":            r.likes,
        "shares":           r.shares,
        "comments_count":   r.comments_count,
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
    return {**_record_dict(r), "image": r.image_data}


def _account_dict(a: CaseAccount) -> dict:
    """Versión liviana de la cuenta (con conteos, sin sus publicaciones)."""
    records = a.records or []
    return {
        "id":          str(a.id),
        "case_id":     str(a.case_id),
        "medium":      a.medium,
        "author":      a.author,
        "profile_url": a.profile_url,
        "user_id":     a.user_id,
        "account_age_months": a.account_age_months,
        "followers":   a.followers,
        "following":   a.following,
        "verified":    a.verified,
        "bio":         a.bio,
        "city":        a.city,
        "account_removed":     a.account_removed,
        "removed_date":        a.removed_date.isoformat() if a.removed_date else None,
        "created_new_account": a.created_new_account,
        "new_account_info":    a.new_account_info,
        "record_count": len(records),
        "denounced":    any(r.reported is True for r in records),
        "posts_removed_count": sum(1 for r in records if r.post_removed is True),
        "created_by":   str(a.created_by),
        "created_at":   a.created_at.isoformat() if a.created_at else None,
        "updated_at":   a.updated_at.isoformat() if a.updated_at else None,
    }


def _account_detail_dict(a: CaseAccount) -> dict:
    records = sorted(a.records or [], key=lambda r: (r.post_id or 0, r.created_at or datetime.min))
    return {**_account_dict(a), "records": [_record_dict(r) for r in records]}


def _case_dict(c: Case) -> dict:
    accounts = c.accounts or []
    accounts_removed = sum(1 for a in accounts if a.account_removed is True)
    accounts_denounced = sum(
        1 for a in accounts if any(r.reported is True for r in (a.records or []))
    )
    record_count = sum(len(a.records or []) for a in accounts)
    return {
        "id":              str(c.id),
        "name":            c.name,
        "has_image":       bool(c.image_data),
        "account_count":   len(accounts),
        "accounts_removed_count":   accounts_removed,
        "accounts_denounced_count": accounts_denounced,
        "record_count":    record_count,
        "created_by":      str(c.created_by),
        "created_by_name": c.creator.full_name if c.creator else None,
        "created_at":      c.created_at.isoformat() if c.created_at else None,
        "updated_at":      c.updated_at.isoformat() if c.updated_at else None,
    }


def _case_detail_dict(c: Case) -> dict:
    accounts = sorted(c.accounts or [], key=lambda a: (a.medium or "", a.created_at or datetime.min))
    return {**_case_dict(c), "image": c.image_data, "accounts": [_account_dict(a) for a in accounts]}


# ── Getters ───────────────────────────────────────────────────

def _get_case_or_404(db: Session, case_id: uuid.UUID) -> Case:
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    return c


def _get_account_or_404(db: Session, case_id: uuid.UUID, account_id: uuid.UUID) -> CaseAccount:
    a = (
        db.query(CaseAccount)
        .filter(CaseAccount.id == account_id, CaseAccount.case_id == case_id)
        .first()
    )
    if not a:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return a


def _get_record_or_404(db: Session, account_id: uuid.UUID, record_id: uuid.UUID) -> CaseRecord:
    r = (
        db.query(CaseRecord)
        .filter(CaseRecord.id == record_id, CaseRecord.account_id == account_id)
        .first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    return r


# ── Aplicación de campos ──────────────────────────────────────

_ACCOUNT_TEXT = ("author", "profile_url", "user_id", "account_age_months", "bio", "city", "new_account_info")
_ACCOUNT_PASS = ("followers", "following", "verified", "account_removed", "removed_date", "created_new_account")


def _apply_account_fields(a: CaseAccount, fields: dict) -> None:
    for f in _ACCOUNT_TEXT:
        if f in fields:
            setattr(a, f, _clean_str(fields[f]))
    for f in _ACCOUNT_PASS:
        if f in fields:
            setattr(a, f, fields[f])
    if "medium" in fields:
        a.medium = _validate_choice(fields["medium"], CASE_MEDIUMS, "Medio")


_RECORD_TEXT = ("affects", "publication_url", "content_text", "media_type", "reporter_name", "report_detail")
_RECORD_PASS = (
    "publication_date", "likes", "shares", "comments_count",
    "organic_criticism", "opposition_criticism", "coordinated_attack", "reported", "post_removed",
)


def _apply_record_fields(r: CaseRecord, fields: dict) -> None:
    for f in _RECORD_TEXT:
        if f in fields:
            setattr(r, f, _clean_str(fields[f]))
    for f in _RECORD_PASS:
        if f in fields:
            setattr(r, f, fields[f])
    if "sentiment" in fields:
        r.sentiment = _validate_choice(fields["sentiment"], CASE_SENTIMENTS, "Sentimiento")
    if "inauthenticity_flag" in fields:
        r.inauthenticity_flag = _validate_choice(fields["inauthenticity_flag"], CASE_FLAGS, "Semáforo")
    if "image" in fields:
        r.image_data = _validate_image(fields["image"])


# ══════════════════════════════════════════════════════════════
#  Casos
# ══════════════════════════════════════════════════════════════

@router.get("")
def list_cases(db: Session = Depends(get_db), _: User = Depends(require_case_manager)):
    cases = db.query(Case).order_by(Case.created_at.desc()).all()
    return [_case_dict(c) for c in cases]


@router.get("/{case_id}")
def get_case(case_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_case_manager)):
    return _case_detail_dict(_get_case_or_404(db, case_id))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_case(
    request: Request, data: CaseCreate,
    db: Session = Depends(get_db), user: User = Depends(require_case_manager),
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
    request: Request, case_id: uuid.UUID, data: CaseUpdate,
    db: Session = Depends(get_db), user: User = Depends(require_case_manager),
):
    c = _get_case_or_404(db, case_id)
    fields = data.model_dump(exclude_unset=True)
    if "name" in fields and fields["name"] is not None:
        new_name = fields["name"].strip()
        if not new_name:
            raise HTTPException(status_code=422, detail="El nombre del caso no puede quedar vacío")
        c.name = new_name
    if "image" in fields:
        c.image_data = _validate_image(fields["image"])
    log_action(db, user.id, "case_updated", request, "cases", c.id, {"name": c.name})
    db.commit()
    db.refresh(c)
    return _case_detail_dict(c)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    request: Request, case_id: uuid.UUID,
    db: Session = Depends(get_db), user: User = Depends(require_case_manager),
):
    c = _get_case_or_404(db, case_id)
    log_action(db, user.id, "case_deleted", request, "cases", c.id, {"name": c.name})
    db.delete(c)                                 # cascade → cuentas → publicaciones
    db.commit()


# ══════════════════════════════════════════════════════════════
#  Cuentas de un caso
# ══════════════════════════════════════════════════════════════

@router.get("/{case_id}/accounts/{account_id}")
def get_account(
    case_id: uuid.UUID, account_id: uuid.UUID,
    db: Session = Depends(get_db), _: User = Depends(require_case_manager),
):
    return _account_detail_dict(_get_account_or_404(db, case_id, account_id))


@router.post("/{case_id}/accounts", status_code=status.HTTP_201_CREATED)
def create_account(
    request: Request, case_id: uuid.UUID, data: AccountCreate,
    db: Session = Depends(get_db), user: User = Depends(require_case_manager),
):
    c = _get_case_or_404(db, case_id)
    a = CaseAccount(case_id=c.id, created_by=user.id)
    _apply_account_fields(a, data.model_dump(exclude_unset=True))
    db.add(a)
    db.flush()
    log_action(db, user.id, "case_account_created", request, "case_accounts", a.id,
               {"case": c.name, "medium": a.medium})
    db.commit()
    db.refresh(a)
    return _account_detail_dict(a)


@router.put("/{case_id}/accounts/{account_id}")
def update_account(
    request: Request, case_id: uuid.UUID, account_id: uuid.UUID, data: AccountUpdate,
    db: Session = Depends(get_db), user: User = Depends(require_case_manager),
):
    a = _get_account_or_404(db, case_id, account_id)
    _apply_account_fields(a, data.model_dump(exclude_unset=True))
    log_action(db, user.id, "case_account_updated", request, "case_accounts", a.id, None)
    db.commit()
    db.refresh(a)
    return _account_detail_dict(a)


@router.delete("/{case_id}/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    request: Request, case_id: uuid.UUID, account_id: uuid.UUID,
    db: Session = Depends(get_db), user: User = Depends(require_case_manager),
):
    a = _get_account_or_404(db, case_id, account_id)
    log_action(db, user.id, "case_account_deleted", request, "case_accounts", a.id, None)
    db.delete(a)                                 # cascade → publicaciones
    db.commit()


# ══════════════════════════════════════════════════════════════
#  Publicaciones de una cuenta
# ══════════════════════════════════════════════════════════════

@router.get("/{case_id}/accounts/{account_id}/records/{record_id}")
def get_record(
    case_id: uuid.UUID, account_id: uuid.UUID, record_id: uuid.UUID,
    db: Session = Depends(get_db), _: User = Depends(require_case_manager),
):
    _get_account_or_404(db, case_id, account_id)
    return _record_detail_dict(_get_record_or_404(db, account_id, record_id))


@router.post("/{case_id}/accounts/{account_id}/records", status_code=status.HTTP_201_CREATED)
def create_record(
    request: Request, case_id: uuid.UUID, account_id: uuid.UUID, data: RecordCreate,
    db: Session = Depends(get_db), user: User = Depends(require_case_manager),
):
    a = _get_account_or_404(db, case_id, account_id)
    next_post_id = (db.query(func.max(CaseRecord.post_id)).scalar() or 0) + 1  # consecutivo global
    r = CaseRecord(account_id=a.id, case_id=a.case_id, created_by=user.id, post_id=next_post_id)
    _apply_record_fields(r, data.model_dump(exclude_unset=True))
    db.add(r)
    db.flush()
    log_action(db, user.id, "case_record_created", request, "case_records", r.id, {"post_id": r.post_id})
    db.commit()
    db.refresh(r)
    return _record_detail_dict(r)


@router.put("/{case_id}/accounts/{account_id}/records/{record_id}")
def update_record(
    request: Request, case_id: uuid.UUID, account_id: uuid.UUID, record_id: uuid.UUID, data: RecordUpdate,
    db: Session = Depends(get_db), user: User = Depends(require_case_manager),
):
    _get_account_or_404(db, case_id, account_id)
    r = _get_record_or_404(db, account_id, record_id)
    _apply_record_fields(r, data.model_dump(exclude_unset=True))
    log_action(db, user.id, "case_record_updated", request, "case_records", r.id, None)
    db.commit()
    db.refresh(r)
    return _record_detail_dict(r)


@router.delete("/{case_id}/accounts/{account_id}/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(
    request: Request, case_id: uuid.UUID, account_id: uuid.UUID, record_id: uuid.UUID,
    db: Session = Depends(get_db), user: User = Depends(require_case_manager),
):
    _get_account_or_404(db, case_id, account_id)
    r = _get_record_or_404(db, account_id, record_id)
    log_action(db, user.id, "case_record_deleted", request, "case_records", r.id, None)
    db.delete(r)
    db.commit()
