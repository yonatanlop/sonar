import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.alert import Alert as AlertModel
from app.models.bot import BotAnalysis, AccountProfile
from app.models.entity import Entity
from app.models.mention import Mention, SocialPlatform
from app.models.sentiment_feedback import SentimentFeedback
from app.workers.nlp.urgency import compute_urgency_score

VALID_SENTIMENT_LABELS = {"positive", "neutral", "negative", "very_negative"}


class FeedbackIn(BaseModel):
    corrected_label: str
    notes: Optional[str] = None

router = APIRouter(prefix="/mentions", tags=["Menciones"])

PAGE_SIZE = 20


def _mention_dict(m: Mention, db: Session) -> dict:
    # Determinar si el autor es bot
    account = db.query(AccountProfile).filter(
        AccountProfile.platform_id == m.platform_id,
        AccountProfile.external_user_id == m.author_ext_id,
    ).first()

    bot_label = None
    bot_score = None
    if account:
        latest = (db.query(BotAnalysis)
                  .filter(BotAnalysis.account_profile_id == account.id)
                  .order_by(BotAnalysis.analyzed_at.desc())
                  .first())
        if latest:
            bot_label = latest.classification
            bot_score = float(latest.bot_score)

    is_bot = bot_label == "bot"

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
        "urgency_score":      float(m.urgency_score) if m.urgency_score is not None else 0.0,
        "is_bot":             is_bot,
        "bot_label":          bot_label,                                        # real|anonymous|suspicious|bot
        "bot_score":          bot_score,                                        # 0.0 - 1.0
        "author_followers":   account.followers_count if account else None,
        "author_location":    account.location_text if account else None,
        "conversation_id":    m.conversation_id,
        "is_duplicate":       m.is_duplicate,
        "media_urls":         m.media_urls,
        "visual_match":       m.visual_match,
        "visual_match_names": m.visual_match_names,
        "is_attended":        (db.query(AlertModel)
                                 .filter(AlertModel.mention_id == m.id,
                                         AlertModel.acknowledged == True)
                                 .first()) is not None,
    }


@router.get("")
def list_mentions(
    entity_id:  Optional[uuid.UUID] = Query(None),
    platform:   Optional[str]       = Query(None),
    sentiment:  Optional[str]       = Query(None),
    language:   Optional[str]       = Query(None),
    hate_only:         bool             = Query(False),
    min_urgency:       Optional[float]  = Query(None, ge=0, le=100, description="Filtrar menciones con urgency_score >= valor (0-100)"),
    exclude_duplicates: bool            = Query(False, description="Excluir menciones marcadas como duplicados semánticos"),
    visual_only:        bool            = Query(False, description="Solo menciones con coincidencia visual detectada"),
    bot_filter:        Optional[str]   = Query(None, description="Filtrar por clasificación de bot: bot|suspicious|real|anonymous"),
    min_bot_score:     Optional[float] = Query(None, ge=0.0, le=1.0, description="Filtrar menciones cuyo autor tiene bot_probability >= valor"),
    country:           Optional[str]   = Query(None, description="Filtrar por país ISO-2 (ej: CO, MX, US)"),
    date_from:         Optional[str]   = Query(None),
    date_to:           Optional[str]   = Query(None),
    page:              int             = Query(1, ge=1),
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
        if sentiment == 'negative':
            query = query.filter(Mention.sentiment_label.in_(['negative', 'very_negative']))
        else:
            query = query.filter(Mention.sentiment_label == sentiment)

    if language:
        query = query.filter(Mention.language == language)

    if hate_only:
        query = query.filter(Mention.is_hate_speech == True)

    if exclude_duplicates:
        query = query.filter(Mention.is_duplicate == False)

    if visual_only:
        query = query.filter(Mention.visual_match == True)

    if min_urgency is not None:
        query = query.filter(Mention.urgency_score >= min_urgency)

    if country:
        query = query.filter(Mention.country_code == country.upper()[:2])

    if bot_filter:
        from app.models.bot import AccountProfile, BotAnalysis
        from sqlalchemy import exists, and_
        bot_subq = (
            db.query(BotAnalysis.account_profile_id)
            .join(AccountProfile, BotAnalysis.account_profile_id == AccountProfile.id)
            .filter(
                AccountProfile.platform_id == Mention.platform_id,
                AccountProfile.external_user_id == Mention.author_ext_id,
                BotAnalysis.classification == bot_filter,
            )
            .correlate(Mention)
            .exists()
        )
        query = query.filter(bot_subq)

    if min_bot_score is not None:
        from app.models.bot import AccountProfile as _AP
        bot_score_subq = (
            db.query(_AP.id)
            .filter(
                _AP.platform_id == Mention.platform_id,
                _AP.external_user_id == Mention.author_ext_id,
                _AP.bot_probability >= min_bot_score,
            )
            .correlate(Mention)
            .exists()
        )
        query = query.filter(bot_score_subq)

    if date_from:
        query = query.filter(Mention.collected_at >= date_from)

    if date_to:
        query = query.filter(Mention.collected_at <= date_to + "T23:59:59")

    total  = query.count()
    items  = (query
              .order_by(func.coalesce(Mention.published_at, Mention.collected_at).desc())
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


# ── Feedback de sentimiento (corrección por analista) ─────────────────────────

@router.post("/{mention_id}/feedback")
def submit_sentiment_feedback(
    mention_id: uuid.UUID,
    body: FeedbackIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Permite a un analista o administrador corregir la etiqueta de sentimiento
    de una mención. Registra la corrección y recalcula el urgency_score.
    """
    if current_user.role not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="Se requiere rol de analista o administrador")

    if body.corrected_label not in VALID_SENTIMENT_LABELS:
        raise HTTPException(
            status_code=422,
            detail=f"Etiqueta inválida. Permitidos: {', '.join(sorted(VALID_SENTIMENT_LABELS))}",
        )

    mention = db.query(Mention).filter(Mention.id == mention_id).first()
    if not mention:
        raise HTTPException(status_code=404, detail="Mención no encontrada")

    fb = SentimentFeedback(
        mention_id=mention_id,
        original_label=mention.sentiment_label or "neutral",
        corrected_label=body.corrected_label,
        analyst_id=current_user.id,
        notes=body.notes,
    )
    db.add(fb)

    mention.sentiment_label = body.corrected_label
    mention.sentiment_score = Decimal("0.90")
    mention.urgency_score = compute_urgency_score(
        sentiment_label=body.corrected_label,
        sentiment_score=0.90,
        hate_score=float(mention.hate_score) if mention.hate_score else None,
        is_hate_speech=mention.is_hate_speech,
        reach=mention.reach or 0,
    )

    db.commit()
    db.refresh(mention)
    return _mention_dict(mention, db)
