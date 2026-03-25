import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.bot import BotAnalysis, AccountProfile
from app.models.entity import Entity
from app.models.mention import Mention, SocialPlatform

router = APIRouter(prefix="/mentions", tags=["Menciones"])

PAGE_SIZE = 20


def _mention_dict(m: Mention, db: Session) -> dict:
    # Determinar si el autor es bot
    account = db.query(AccountProfile).filter(
        AccountProfile.platform_id == m.platform_id,
        AccountProfile.external_user_id == m.author_ext_id,
    ).first()

    is_bot = False
    if account:
        latest = (db.query(BotAnalysis)
                  .filter(BotAnalysis.account_profile_id == account.id)
                  .order_by(BotAnalysis.analyzed_at.desc())
                  .first())
        is_bot = latest.classification == "bot" if latest else False

    platform = db.query(SocialPlatform).filter(SocialPlatform.id == m.platform_id).first()
    entity   = db.query(Entity).filter(Entity.id == m.entity_id).first()

    return {
        "id":              str(m.id),
        "entity_id":       str(m.entity_id),
        "entity_name":     entity.name if entity else "—",
        "platform_code":   platform.code if platform else None,
        "platform_name":   platform.name if platform else None,
        "external_id":     m.external_id,
        "content":         m.content,
        "author_username": m.author_username,
        "url":             m.url,
        "published_at":    m.published_at.isoformat() if m.published_at else None,
        "collected_at":    m.collected_at.isoformat(),
        "language":        m.language,
        "country_code":    m.country_code,
        "sentiment_label": m.sentiment_label,
        "sentiment_score": float(m.sentiment_score) if m.sentiment_score else None,
        "hate_score":      float(m.hate_score) if m.hate_score else None,
        "is_hate_speech":  m.is_hate_speech,
        "reach":           m.reach,
        "urgency_score":   float(m.urgency_score) if m.urgency_score is not None else 0.0,
        "is_bot":          is_bot,
    }


@router.get("")
def list_mentions(
    entity_id:  Optional[uuid.UUID] = Query(None),
    platform:   Optional[str]       = Query(None),
    sentiment:  Optional[str]       = Query(None),
    language:   Optional[str]       = Query(None),
    hate_only:    bool                = Query(False),
    min_urgency:  Optional[float]    = Query(None, ge=0, le=100, description="Filtrar menciones con urgency_score >= valor (0-100)"),
    date_from:    Optional[str]      = Query(None),
    date_to:      Optional[str]      = Query(None),
    page:         int                = Query(1, ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(Mention)

    if entity_id:
        query = query.filter(Mention.entity_id == entity_id)

    if platform:
        platform_obj = db.query(SocialPlatform).filter(SocialPlatform.code == platform).first()
        if platform_obj:
            query = query.filter(Mention.platform_id == platform_obj.id)

    if sentiment:
        query = query.filter(Mention.sentiment_label == sentiment)

    if language:
        query = query.filter(Mention.language == language)

    if hate_only:
        query = query.filter(Mention.is_hate_speech == True)

    if min_urgency is not None:
        query = query.filter(Mention.urgency_score >= min_urgency)

    if date_from:
        query = query.filter(Mention.collected_at >= date_from)

    if date_to:
        query = query.filter(Mention.collected_at <= date_to + "T23:59:59")

    total  = query.count()
    items  = (query
              .order_by(Mention.collected_at.desc())
              .offset((page - 1) * PAGE_SIZE)
              .limit(PAGE_SIZE)
              .all())

    return {
        "total": total,
        "page":  page,
        "pages": (total + PAGE_SIZE - 1) // PAGE_SIZE,
        "items": [_mention_dict(m, db) for m in items],
    }


# ── Búsqueda semántica (v2 — módulo 6.1) ─────────────────────────

@router.get("/search")
def semantic_search_mentions(
    q: str                       = Query(..., min_length=3, description="Texto de búsqueda semántica"),
    entity_id: Optional[uuid.UUID] = Query(None),
    limit: int                   = Query(20, ge=5, le=50),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Búsqueda semántica de menciones por similitud de contenido.
    Usa embeddings 384-dim (paraphrase-multilingual-MiniLM-L12-v2) + pgvector coseno.
    Requiere HUGGINGFACE_TOKEN configurado; retorna lista vacía si no hay token.
    """
    from app.core.config import settings
    from app.workers.nlp.embeddings import semantic_search

    if not settings.HUGGINGFACE_TOKEN:
        return {"query": q, "results": [], "note": "Requiere HUGGINGFACE_TOKEN"}

    results = semantic_search(db, q, settings.HUGGINGFACE_TOKEN,
                              entity_id=entity_id, limit=limit)

    return {"query": q, "total": len(results), "results": results}
