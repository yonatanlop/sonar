import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_analyst
from app.database import get_db
from app.models.anomaly import Anomaly
from app.models.entity import Country, Entity, EntityAlias, EntityType, Keyword
from app.models.mention import Mention
from app.models.summary import DailySummary
from app.models.user import User

router = APIRouter(prefix="/entities", tags=["Entidades"])


# ── Schemas ───────────────────────────────────────────────────

class EntityCreate(BaseModel):
    name: str
    entity_type_id: int
    country_code: Optional[str] = None
    description: Optional[str] = None
    photo_url: Optional[str] = None


class EntityPatch(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None
    description: Optional[str] = None
    photo_url: Optional[str] = None


class AliasCreate(BaseModel):
    alias: str


class KeywordCreate(BaseModel):
    keyword: str
    language: str = "es"
    weight: int = 1


# ── Helpers ───────────────────────────────────────────────────

def _risk_level(negative_pct: float) -> str:
    if negative_pct >= 66: return "alto"
    if negative_pct >= 36: return "medio"
    return "bajo"


def _entity_dict(entity: Entity, db: Session) -> dict:
    since_today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    mention_count = db.query(func.count(Mention.id)).filter(
        Mention.entity_id == entity.id,
        Mention.collected_at >= since_today,
    ).scalar() or 0

    neg_count = db.query(func.count(Mention.id)).filter(
        Mention.entity_id == entity.id,
        Mention.collected_at >= since_today,
        Mention.sentiment_label.in_(["negative", "very_negative"]),
    ).scalar() or 0

    neg_pct    = (neg_count / mention_count * 100) if mention_count else 0
    risk_level = _risk_level(neg_pct) if mention_count >= 5 else None

    return {
        "id":           str(entity.id),
        "name":         entity.name,
        "entity_type_id": entity.entity_type_id,
        "type_name":    entity.entity_type.name if entity.entity_type else None,
        "country_code": entity.country_code,
        "description":  entity.description,
        "photo_url":    entity.photo_url,
        "active":       entity.active,
        "mention_count": mention_count,
        "risk_level":   risk_level,
        "created_at":   entity.created_at.isoformat(),
    }


# ── Catálogos ─────────────────────────────────────────────────

@router.get("/types")
def list_types(db: Session = Depends(get_db), _=Depends(get_current_user)):
    types = db.query(EntityType).order_by(EntityType.name).all()
    return [{"id": t.id, "name": t.name} for t in types]


# ── CRUD Entidades ────────────────────────────────────────────

@router.get("")
def list_entities(
    q: Optional[str] = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(Entity)
    if active_only:
        query = query.filter(Entity.active == True)
    if q:
        query = query.filter(Entity.name.ilike(f"%{q}%"))
    entities = query.order_by(Entity.name).all()
    return [_entity_dict(e, db) for e in entities]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_entity(
    data: EntityCreate,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_db),
):
    if not db.query(EntityType).filter(EntityType.id == data.entity_type_id).first():
        raise HTTPException(status_code=400, detail="Tipo de entidad no existe")

    entity = Entity(**data.model_dump(), created_by=current_user.id)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return _entity_dict(entity, db)


@router.get("/{entity_id}")
def get_entity(
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entidad no encontrada")

    since_7 = datetime.now(timezone.utc) - timedelta(days=7)

    # Estadísticas de 7 días
    rows = db.query(
        Mention.sentiment_label,
        func.count(Mention.id).label("cnt")
    ).filter(
        Mention.entity_id == entity_id,
        Mention.collected_at >= since_7,
        Mention.sentiment_label.isnot(None),
    ).group_by(Mention.sentiment_label).all()

    sentiment = {r.sentiment_label: r.cnt for r in rows}
    total_7   = sum(sentiment.values())

    return {
        **_entity_dict(entity, db),
        "aliases":  [{"id": str(a.id), "alias": a.alias} for a in entity.aliases],
        "keywords": [
            {"id": str(k.id), "keyword": k.keyword,
             "language": k.language, "weight": k.weight, "active": k.active}
            for k in entity.keywords
        ],
        "stats_7d": {
            "total": total_7,
            "sentiment": sentiment,
            "negative_pct": round(
                (sentiment.get("negative", 0) + sentiment.get("very_negative", 0))
                / total_7 * 100, 1
            ) if total_7 else 0,
        },
    }


@router.patch("/{entity_id}")
def patch_entity(
    entity_id: uuid.UUID,
    data: EntityPatch,
    _=Depends(require_analyst),
    db: Session = Depends(get_db),
):
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entidad no encontrada")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(entity, field, value)
    db.commit()
    db.refresh(entity)
    return _entity_dict(entity, db)


# ── Alias ─────────────────────────────────────────────────────

@router.post("/{entity_id}/aliases", status_code=status.HTTP_201_CREATED)
def add_alias(
    entity_id: uuid.UUID,
    data: AliasCreate,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_db),
):
    if not db.query(Entity).filter(Entity.id == entity_id).first():
        raise HTTPException(status_code=404, detail="Entidad no encontrada")
    alias = EntityAlias(entity_id=entity_id, alias=data.alias, created_by=current_user.id)
    db.add(alias)
    db.commit()
    db.refresh(alias)
    return {"id": str(alias.id), "alias": alias.alias}


@router.delete("/{entity_id}/aliases/{alias_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alias(
    entity_id: uuid.UUID,
    alias_id: uuid.UUID,
    _=Depends(require_analyst),
    db: Session = Depends(get_db),
):
    alias = db.query(EntityAlias).filter(
        EntityAlias.id == alias_id, EntityAlias.entity_id == entity_id
    ).first()
    if not alias:
        raise HTTPException(status_code=404, detail="Alias no encontrado")
    db.delete(alias)
    db.commit()


# ── Keywords ──────────────────────────────────────────────────

@router.post("/{entity_id}/keywords", status_code=status.HTTP_201_CREATED)
def add_keyword(
    entity_id: uuid.UUID,
    data: KeywordCreate,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_db),
):
    if not db.query(Entity).filter(Entity.id == entity_id).first():
        raise HTTPException(status_code=404, detail="Entidad no encontrada")
    keyword = Keyword(entity_id=entity_id, created_by=current_user.id, **data.model_dump())
    db.add(keyword)
    db.commit()
    db.refresh(keyword)
    return {"id": str(keyword.id), "keyword": keyword.keyword,
            "language": keyword.language, "weight": keyword.weight}


@router.delete("/{entity_id}/keywords/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_keyword(
    entity_id: uuid.UUID,
    keyword_id: uuid.UUID,
    _=Depends(require_analyst),
    db: Session = Depends(get_db),
):
    kw = db.query(Keyword).filter(
        Keyword.id == keyword_id, Keyword.entity_id == entity_id
    ).first()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword no encontrada")
    db.delete(kw)
    db.commit()


# ── Anomalías (v2) ─────────────────────────────────────────────

@router.get("/{entity_id}/anomalies")
def get_entity_anomalies(
    entity_id: uuid.UUID,
    days: int = Query(7, ge=1, le=30, description="Número de días hacia atrás"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Retorna las anomalías detectadas para la entidad en los últimos N días.
    """
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entidad no encontrada")

    since = datetime.now(timezone.utc) - timedelta(days=days)
    anomalies = (
        db.query(Anomaly)
        .filter(
            Anomaly.entity_id   == entity_id,
            Anomaly.detected_at >= since,
        )
        .order_by(Anomaly.detected_at.desc())
        .limit(50)
        .all()
    )

    return {
        "entity_id":   str(entity_id),
        "entity_name": entity.name,
        "days":        days,
        "total":       len(anomalies),
        "items": [
            {
                "id":           str(a.id),
                "detected_at":  a.detected_at.isoformat(),
                "metric":       a.metric,
                "z_score":      round(a.z_score, 2),
                "value":        round(a.value, 1),
                "baseline":     round(a.baseline, 1),
                "std_dev":      round(a.std_dev, 2),
                "severity":     "critical" if a.z_score >= 4 else "high" if a.z_score >= 3 else "medium",
            }
            for a in anomalies
        ],
    }


# ── Resúmenes diarios (v2) ─────────────────────────────────────

@router.get("/{entity_id}/summaries")
def get_entity_summaries(
    entity_id: uuid.UUID,
    limit: int = Query(7, ge=1, le=30, description="Número de resúmenes a retornar"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Retorna los últimos N resúmenes diarios generados por IA para la entidad.
    """
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entidad no encontrada")

    summaries = (
        db.query(DailySummary)
        .filter(DailySummary.entity_id == entity_id)
        .order_by(DailySummary.summary_date.desc())
        .limit(limit)
        .all()
    )

    return {
        "entity_id":   str(entity_id),
        "entity_name": entity.name,
        "total":       len(summaries),
        "items": [
            {
                "id":            str(s.id),
                "summary_date":  s.summary_date.isoformat(),
                "summary_text":  s.summary_text,
                "model_used":    s.model_used,
                "mention_count": s.mention_count,
                "generated_at":  s.generated_at.isoformat(),
            }
            for s in summaries
        ],
    }


@router.post("/{entity_id}/summaries/generate", status_code=200)
def trigger_summary(
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=Depends(require_analyst),
):
    """
    Genera manualmente el resumen del día para la entidad (útil para testing).
    Requiere GROQ_API_KEY configurada.
    """
    from app.core.config import settings
    if not settings.GROQ_API_KEY:
        raise HTTPException(
            status_code=422,
            detail="GROQ_API_KEY no está configurada en .env",
        )

    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entidad no encontrada")

    from app.workers.nlp.summarizer import summarize_entity
    result = summarize_entity(db, entity)
    db.commit()

    if not result:
        raise HTTPException(
            status_code=422,
            detail="No hay suficientes menciones hoy para generar un resumen (mínimo 3).",
        )

    return {
        "id":            str(result.id),
        "summary_date":  result.summary_date.isoformat(),
        "summary_text":  result.summary_text,
        "model_used":    result.model_used,
        "mention_count": result.mention_count,
    }


# ── Topics / Temas (v2) ────────────────────────────────────────

@router.get("/{entity_id}/topics")
def get_entity_topics(
    entity_id: uuid.UUID,
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Devuelve la distribución de temas detectados para la entidad
    en los últimos N días, agrupados por topic_label.
    """
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entidad no encontrada")

    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        db.query(
            Mention.topic_id,
            Mention.topic_label,
            func.count(Mention.id).label("count"),
        )
        .filter(
            Mention.entity_id    == entity_id,
            Mention.collected_at >= since,
            Mention.topic_id.isnot(None),
        )
        .group_by(Mention.topic_id, Mention.topic_label)
        .order_by(func.count(Mention.id).desc())
        .all()
    )

    total = sum(r.count for r in rows)

    return {
        "entity_id":   str(entity_id),
        "entity_name": entity.name,
        "days":        days,
        "total_labeled": total,
        "topics": [
            {
                "topic_id": r.topic_id,
                "label":    r.topic_label,
                "count":    r.count,
                "pct":      round(r.count / total * 100, 1) if total else 0,
            }
            for r in rows
        ],
    }


@router.post("/{entity_id}/topics/analyze", status_code=200)
def trigger_topic_analysis(
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=Depends(require_analyst),
):
    """Ejecuta topic modeling manualmente para la entidad."""
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entidad no encontrada")

    from app.workers.nlp.topics import detect_topics_for_entity
    result = detect_topics_for_entity(db, entity)
    db.commit()

    if result.get("status") != "ok":
        raise HTTPException(
            status_code=422,
            detail=f"No se pudo detectar temas: {result.get('reason', 'unknown')}",
        )
    return result
