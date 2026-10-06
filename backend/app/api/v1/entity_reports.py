"""
Informe de actividad de entidades: días con más menciones, keywords más usadas, cuentas
que las publican (con referencia a Rizoma) y eventos del día registrados por el equipo.

Fechas: día calendario de Colombia (ver app/core/timezone.py). Se usa la fecha de publicación
de la mención y, si no existe, la de recolección. Solo cuentan menciones relevantes
(is_relevant), igual que el resto del sistema.
"""
import uuid
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.audit_utils import log_action
from app.api.deps import get_current_user, require_analyst
from app.core.timezone import co_date_end, co_date_start, co_midnight
from app.database import get_db
from app.models.case import Case, CaseAccount
from app.models.entity import Entity, Keyword
from app.models.entity_event import EntityDayEvent
from app.models.mention import Mention, SocialPlatform, mention_keywords
from app.models.user import User

router = APIRouter(prefix="/entity-reports", tags=["Informe de entidades"])

BOGOTA = "America/Bogota"
DEFAULT_DAYS = 90
TOP_ACCOUNTS = 25
TOP_KEYWORDS = 25
TOP_PEAKS = 10

# Código de plataforma (tabla social_platforms) → nombre de la red en Rizoma (CaseAccount.medium)
RIZOMA_MEDIUM = {
    "twitter": "X", "facebook": "Facebook", "instagram": "Instagram",
    "tiktok": "TikTok", "youtube": "YouTube",
}


class EventCreate(BaseModel):
    entity_id: uuid.UUID
    event_date: date
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None


def _mention_day():
    return func.date(func.timezone(BOGOTA, func.coalesce(Mention.published_at, Mention.collected_at)))


def _conditions(entity_ids, date_from: str, date_to: str):
    ts = func.coalesce(Mention.published_at, Mention.collected_at)
    return [
        Mention.entity_id.in_(entity_ids),
        Mention.is_relevant.is_(True),
        ts >= co_date_start(date_from),
        ts <= co_date_end(date_to),
    ]


def _handle(value: str) -> str:
    return value.strip().lstrip("@").lower()


def _rizoma_index(db: Session):
    """Cuentas de Rizoma indexadas por red + identificador. En Rizoma el @usuario suele estar en
    `user_id` (y `author` es el nombre para mostrar), así que se indexan ambos, más el id numérico."""
    by_handle, by_name, by_numeric = {}, {}, {}
    rows = db.query(CaseAccount, Case.name).join(Case, Case.id == CaseAccount.case_id).all()
    for acc, case_name in rows:
        info = {
            "case_id": str(acc.case_id), "case_name": case_name, "account_id": str(acc.id),
            "medium": acc.medium, "account_removed": bool(acc.account_removed),
        }
        if acc.user_id:
            by_handle.setdefault((acc.medium, _handle(acc.user_id)), info)
            if acc.user_id.strip().isdigit():
                by_numeric.setdefault((acc.medium, acc.user_id.strip()), info)
        if acc.author:
            by_name.setdefault((acc.medium, _handle(acc.author)), info)
    return by_handle, by_name, by_numeric


@router.get("")
def entity_activity_report(
    entity_ids: str = Query(..., description="IDs de entidades separados por coma"),
    date_from: str = Query("", description="AAAA-MM-DD (por defecto, hace 90 días)"),
    date_to: str = Query("", description="AAAA-MM-DD (por defecto, hoy)"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        ids = [uuid.UUID(x.strip()) for x in entity_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="IDs de entidad inválidos")
    if not ids:
        raise HTTPException(status_code=422, detail="Selecciona al menos una entidad")

    if not date_to:
        date_to = co_midnight().strftime("%Y-%m-%d")
    if not date_from:
        date_from = (co_midnight() - timedelta(days=DEFAULT_DAYS - 1)).strftime("%Y-%m-%d")
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="La fecha inicial es posterior a la final")

    entities = db.query(Entity).filter(Entity.id.in_(ids)).all()
    names = {e.id: e.name for e in entities}
    platforms = {p.id: p.code for p in db.query(SocialPlatform).all()}
    conds = _conditions(ids, date_from, date_to)

    day = _mention_day()
    daily_rows = (db.query(day.label("d"), func.count(Mention.id))
                  .filter(*conds).group_by(day).order_by(day).all())
    daily = [{"date": d.isoformat(), "count": n} for d, n in daily_rows if d is not None]
    total = sum(p["count"] for p in daily)

    by_year = Counter()
    by_month = Counter()
    for p in daily:
        by_year[p["date"][:4]] += p["count"]
        by_month[p["date"][:7]] += p["count"]
    peaks = sorted(daily, key=lambda p: p["count"], reverse=True)[:TOP_PEAKS]

    kw_rows = (db.query(Keyword.keyword, Keyword.keyword_secondary, Mention.entity_id, func.count(Mention.id))
               .select_from(mention_keywords)
               .join(Mention, Mention.id == mention_keywords.c.mention_id)
               .join(Keyword, Keyword.id == mention_keywords.c.keyword_id)
               .filter(*conds, Keyword.entity_id == Mention.entity_id)
               .group_by(Keyword.keyword, Keyword.keyword_secondary, Mention.entity_id)
               .order_by(func.count(Mention.id).desc())
               .limit(TOP_KEYWORDS).all())
    keywords = [{
        "keyword": kw + (f" + {sec}" if sec else ""),
        "entity_name": names.get(eid, ""), "count": n,
    } for kw, sec, eid, n in kw_rows]

    acc_rows = (db.query(SocialPlatform.code, Mention.author_username, Mention.author_ext_id,
                         Mention.entity_id, func.count(Mention.id))
                .select_from(Mention)
                .join(SocialPlatform, SocialPlatform.id == Mention.platform_id)
                .filter(*conds, Mention.author_username.isnot(None))
                .group_by(SocialPlatform.code, Mention.author_username, Mention.author_ext_id, Mention.entity_id)
                .order_by(func.count(Mention.id).desc())
                .limit(TOP_ACCOUNTS).all())
    by_handle, by_name, by_numeric = _rizoma_index(db)
    accounts = []
    for code, username, ext_id, eid, n in acc_rows:
        medium = RIZOMA_MEDIUM.get(code)
        rizoma = None
        if medium:
            if ext_id and str(ext_id).strip().isdigit():
                rizoma = by_numeric.get((medium, str(ext_id).strip()))
            if rizoma is None:
                rizoma = by_handle.get((medium, _handle(username)))
            if rizoma is None:
                rizoma = by_name.get((medium, _handle(username)))
        accounts.append({
            "platform": code, "author": username, "mentions": n,
            "entity_name": names.get(eid, ""), "rizoma": rizoma,
        })

    ev_rows = (db.query(EntityDayEvent, User.full_name, Entity.name)
               .join(User, User.id == EntityDayEvent.created_by)
               .join(Entity, Entity.id == EntityDayEvent.entity_id)
               .filter(EntityDayEvent.entity_id.in_(ids),
                       EntityDayEvent.event_date >= date.fromisoformat(date_from),
                       EntityDayEvent.event_date <= date.fromisoformat(date_to))
               .order_by(EntityDayEvent.event_date.desc(), EntityDayEvent.created_at.desc()).all())
    events = [{
        "id": str(ev.id), "entity_id": str(ev.entity_id), "entity_name": ename,
        "date": ev.event_date.isoformat(), "title": ev.title, "description": ev.description,
        "created_by": who, "created_at": ev.created_at.isoformat() if ev.created_at else None,
    } for ev, who, ename in ev_rows]

    active_days = len(daily)
    return {
        "entities": [{"id": str(e.id), "name": e.name} for e in entities],
        "date_from": date_from,
        "date_to": date_to,
        "total": total,
        "active_days": active_days,
        "daily": daily,
        "peaks": peaks,
        "by_year": [{"year": y, "count": c} for y, c in sorted(by_year.items())],
        "by_month": [{"month": m, "count": c} for m, c in sorted(by_month.items())],
        "events": events,
        "keywords": keywords,
        "accounts": accounts,
    }


@router.post("/events", status_code=status.HTTP_201_CREATED)
def create_day_event(
    request: Request, data: EventCreate,
    db: Session = Depends(get_db), user: User = Depends(require_analyst),
):
    if not db.query(Entity.id).filter(Entity.id == data.entity_id).first():
        raise HTTPException(status_code=404, detail="Entidad no encontrada")
    ev = EntityDayEvent(
        entity_id=data.entity_id, event_date=data.event_date, title=data.title.strip(),
        description=(data.description or "").strip() or None, created_by=user.id,
    )
    db.add(ev)
    db.flush()
    log_action(db, user.id, "entity_day_event_added", request, "entities", data.entity_id,
               {"date": data.event_date.isoformat(), "title": ev.title})
    db.commit()
    return {"id": str(ev.id)}


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_day_event(
    request: Request, event_id: uuid.UUID,
    db: Session = Depends(get_db), user: User = Depends(require_analyst),
):
    ev = db.query(EntityDayEvent).filter(EntityDayEvent.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    log_action(db, user.id, "entity_day_event_deleted", request, "entities", ev.entity_id,
               {"date": ev.event_date.isoformat(), "title": ev.title})
    db.delete(ev)
    db.commit()
