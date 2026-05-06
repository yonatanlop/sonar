"""
Twitter Explorer — API de feeds de @usuarios y #hashtags.

Permite monitorear cuentas de Twitter y hashtags de forma independiente
al sistema de entidades principal.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.audit_utils import log_action
from app.api.deps import get_current_user, require_analyst
from app.database import get_db
from app.models.entity import Entity, EntityType
from app.models.mention import Mention, SocialPlatform
from app.models.twitter_feed import TwitterFeed
from app.models.user import User

router = APIRouter(prefix="/twitter-feeds", tags=["Twitter Explorer"])


# ── Schemas ───────────────────────────────────────────────────

class FeedCreate(BaseModel):
    feed_type: str   # 'user' | 'hashtag' | 'keyword'
    term: str        # username sin @, hashtag sin #, o keyword libre


class FeedResponse(BaseModel):
    id: str
    feed_type: str
    term: str
    display_name: str
    entity_id: Optional[str]
    active: bool
    mention_count: int
    last_mention_at: Optional[str]


# ── Helpers ───────────────────────────────────────────────────

def _display_name(feed_type: str, term: str) -> str:
    if feed_type == "user":
        return f"@{term.lstrip('@')}"
    if feed_type == "hashtag":
        return f"#{term.lstrip('#')}"
    return term


def _clean_term(feed_type: str, term: str) -> str:
    """Normaliza el término: sin @ ni # iniciales."""
    term = term.strip()
    if feed_type == "user":
        return term.lstrip("@")
    if feed_type == "hashtag":
        return term.lstrip("#")
    return term


def _get_or_create_monitor_entity_type(db: Session) -> int:
    et = db.query(EntityType).filter(EntityType.name == "Monitor Twitter").first()
    if not et:
        et = EntityType(name="Monitor Twitter")
        db.add(et)
        db.flush()
    return et.id


def _feed_to_dict(feed: TwitterFeed, db: Session) -> dict:
    twitter_platform = db.query(SocialPlatform).filter(SocialPlatform.code == "twitter").first()

    mention_count = 0
    last_mention_at = None
    if feed.entity_id and twitter_platform:
        mention_count = db.query(func.count(Mention.id)).filter(
            Mention.entity_id == feed.entity_id,
            Mention.platform_id == twitter_platform.id,
        ).scalar() or 0

        last_m = (
            db.query(Mention.published_at)
            .filter(
                Mention.entity_id == feed.entity_id,
                Mention.platform_id == twitter_platform.id,
                Mention.published_at.isnot(None),
            )
            .order_by(Mention.published_at.desc())
            .first()
        )
        if last_m:
            last_mention_at = last_m[0].isoformat()

    return {
        "id":              str(feed.id),
        "feed_type":       feed.feed_type,
        "term":            feed.term,
        "display_name":    feed.display_name,
        "entity_id":       str(feed.entity_id) if feed.entity_id else None,
        "active":          feed.active,
        "is_rizoma":       feed.is_rizoma,
        "mention_count":   mention_count,
        "last_mention_at": last_mention_at,
    }


# ── Endpoints ─────────────────────────────────────────────────

@router.get("")
def list_feeds(
    db:   Session = Depends(get_db),
    _:    User    = Depends(get_current_user),
):
    """Lista todos los feeds activos con conteo de menciones."""
    feeds = db.query(TwitterFeed).filter(TwitterFeed.active == True).order_by(TwitterFeed.created_at).all()
    return [_feed_to_dict(f, db) for f in feeds]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_feed(
    request: Request,
    data: FeedCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    """
    Agrega un nuevo feed de @usuario, #hashtag o palabra clave.
    Auto-crea una Entity interna de tipo 'Monitor Twitter'.
    """
    if data.feed_type not in ("user", "hashtag", "keyword"):
        raise HTTPException(status_code=422, detail="feed_type debe ser 'user', 'hashtag' o 'keyword'")

    term = _clean_term(data.feed_type, data.term)
    if not term:
        raise HTTPException(status_code=422, detail="El término no puede estar vacío")

    # Verificar duplicado
    existing = db.query(TwitterFeed).filter(
        TwitterFeed.feed_type == data.feed_type,
        TwitterFeed.term == term,
    ).first()
    if existing:
        if not existing.active:
            existing.active = True
            db.commit()
            return _feed_to_dict(existing, db)
        raise HTTPException(status_code=409, detail=f"Ya existe un monitor para '{_display_name(data.feed_type, term)}'")

    display = _display_name(data.feed_type, term)
    et_id   = _get_or_create_monitor_entity_type(db)

    # Crear Entity interna (no aparece en el listado principal de entidades)
    entity = Entity(
        name=f"[Explorer] {display}",
        entity_type_id=et_id,
        active=True,
        created_by=user.id,
    )
    db.add(entity)
    db.flush()

    feed = TwitterFeed(
        feed_type=data.feed_type,
        term=term,
        display_name=display,
        entity_id=entity.id,
        active=True,
        created_by=user.id,
    )
    db.add(feed)
    db.flush()
    log_action(db, user.id, "twitter_feed_added", request, "twitter_feeds", feed.id,
               {"display_name": display, "feed_type": data.feed_type})
    db.commit()
    db.refresh(feed)

    return _feed_to_dict(feed, db)


@router.patch("/{feed_id}/rizoma")
def toggle_rizoma(
    request: Request,
    feed_id: uuid.UUID,
    db:      Session = Depends(get_db),
    current_user: User = Depends(require_analyst),
):
    """Marca/desmarca un feed como cuenta Rizoma (hostil conocida)."""
    feed = db.query(TwitterFeed).filter(TwitterFeed.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed no encontrado")
    feed.is_rizoma = not feed.is_rizoma
    log_action(db, current_user.id, "twitter_feed_rizoma_toggled", request, "twitter_feeds", feed.id,
               {"display_name": feed.display_name, "is_rizoma": feed.is_rizoma})
    db.commit()
    return _feed_to_dict(feed, db)


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feed(
    request: Request,
    feed_id: uuid.UUID,
    db:      Session = Depends(get_db),
    current_user: User = Depends(require_analyst),
):
    """Desactiva un feed (no elimina las menciones ya recolectadas)."""
    feed = db.query(TwitterFeed).filter(TwitterFeed.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed no encontrado")
    feed.active = False
    log_action(db, current_user.id, "twitter_feed_deleted", request, "twitter_feeds", feed.id,
               {"display_name": feed.display_name, "feed_type": feed.feed_type})
    db.commit()


@router.get("/{feed_id}/mentions")
def get_feed_mentions(
    feed_id:   uuid.UUID,
    sentiment: Optional[str] = Query(None, description="positive|neutral|negative|very_negative"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to:   Optional[str] = Query(None, description="YYYY-MM-DD"),
    page:      int           = Query(1, ge=1),
    db:        Session       = Depends(get_db),
    _:         User          = Depends(get_current_user),
):
    """
    Retorna las menciones (tweets) recolectadas para un feed específico.
    Ordenadas por fecha de publicación descendente.
    """
    from datetime import datetime, timezone
    from app.models.bot import AccountProfile, BotAnalysis

    feed = db.query(TwitterFeed).filter(TwitterFeed.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed no encontrado")

    if not feed.entity_id:
        return {"feed": _feed_to_dict(feed, db), "mentions": [], "total": 0, "page": page}

    twitter_platform = db.query(SocialPlatform).filter(SocialPlatform.code == "twitter").first()

    q = db.query(Mention).filter(
        Mention.entity_id == feed.entity_id,
    )
    if twitter_platform:
        q = q.filter(Mention.platform_id == twitter_platform.id)
    if sentiment:
        q = q.filter(Mention.sentiment_label == sentiment)
    if date_from:
        q = q.filter(Mention.published_at >= datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc))
    if date_to:
        q = q.filter(Mention.published_at <= datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc))

    total = q.count()
    mentions_db = q.order_by(Mention.published_at.desc()).offset((page - 1) * 20).limit(20).all()

    def _m_dict(m: Mention) -> dict:
        urgency = float(m.urgency_score) if m.urgency_score is not None else 0
        return {
            "id":              str(m.id),
            "content":         m.content,
            "author_username": m.author_username,
            "url":             m.url,
            "published_at":    m.published_at.isoformat() if m.published_at else None,
            "sentiment_label": m.sentiment_label,
            "urgency_score":   urgency,
            "reach":           m.reach or 0,
            "language":        m.language,
            "media_urls":      m.media_urls,
        }

    return {
        "feed":     _feed_to_dict(feed, db),
        "mentions": [_m_dict(m) for m in mentions_db],
        "total":    total,
        "page":     page,
        "pages":    max(1, -(-total // 20)),
    }
