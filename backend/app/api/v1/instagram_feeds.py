"""
Instagram Explorer — API de monitores por hashtag o cuenta/usuario.
Mismo patrón que Twitter Explorer (twitter_feeds.py).
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.audit_utils import log_action
from app.api.deps import get_current_user, require_analyst
from app.database import get_db
from app.models.entity import Entity, EntityType
from app.models.instagram_feed import InstagramFeed
from app.models.mention import Mention, SocialPlatform
from app.models.user import User

router = APIRouter(prefix="/instagram-feeds", tags=["Instagram Explorer"])

PLATFORM_CODE = "instagram"
ENTITY_TYPE   = "Monitor Instagram"
VALID_TYPES   = ("hashtag", "account")


# ── Schemas ───────────────────────────────────────────────────

class FeedCreate(BaseModel):
    feed_type: str   # 'hashtag' | 'account'
    term: str


# ── Helpers ───────────────────────────────────────────────────

def _display_name(feed_type: str, term: str) -> str:
    if feed_type == "hashtag":
        return f"#{term.lstrip('#')}"
    return f"@{term.lstrip('@')}"


def _clean_term(feed_type: str, term: str) -> str:
    term = term.strip()
    if feed_type == "hashtag":
        return term.lstrip("#")
    return term.lstrip("@")


def _get_or_create_entity_type(db: Session) -> int:
    et = db.query(EntityType).filter(EntityType.name == ENTITY_TYPE).first()
    if not et:
        et = EntityType(name=ENTITY_TYPE)
        db.add(et)
        db.flush()
    return et.id


def _feed_to_dict(feed: InstagramFeed, db: Session) -> dict:
    platform = db.query(SocialPlatform).filter(SocialPlatform.code == PLATFORM_CODE).first()

    mention_count = 0
    last_mention_at = None
    if feed.entity_id and platform:
        mention_count = db.query(func.count(Mention.id)).filter(
            Mention.entity_id == feed.entity_id,
            Mention.platform_id == platform.id,
        ).scalar() or 0

        last_m = (
            db.query(Mention.published_at)
            .filter(
                Mention.entity_id == feed.entity_id,
                Mention.platform_id == platform.id,
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
    db: Session = Depends(get_db),
    _:  User    = Depends(get_current_user),
):
    feeds = db.query(InstagramFeed).filter(InstagramFeed.active == True).order_by(InstagramFeed.created_at).all()
    return [_feed_to_dict(f, db) for f in feeds]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_feed(
    request: Request,
    data: FeedCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    if data.feed_type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"feed_type debe ser uno de {VALID_TYPES}")

    term = _clean_term(data.feed_type, data.term)
    if not term:
        raise HTTPException(status_code=422, detail="El término no puede estar vacío")

    existing = db.query(InstagramFeed).filter(
        InstagramFeed.feed_type == data.feed_type,
        InstagramFeed.term == term,
    ).first()
    if existing:
        if not existing.active:
            existing.active = True
            db.commit()
            return _feed_to_dict(existing, db)
        raise HTTPException(status_code=409, detail=f"Ya existe un monitor para '{_display_name(data.feed_type, term)}'")

    display = _display_name(data.feed_type, term)
    et_id   = _get_or_create_entity_type(db)

    entity = Entity(
        name=f"[Explorer] IG {display}",
        entity_type_id=et_id,
        active=True,
        created_by=user.id,
    )
    db.add(entity)
    db.flush()

    feed = InstagramFeed(
        feed_type=data.feed_type,
        term=term,
        display_name=display,
        entity_id=entity.id,
        active=True,
        created_by=user.id,
    )
    db.add(feed)
    db.flush()
    log_action(db, user.id, "instagram_feed_added", request, "instagram_feeds", feed.id,
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
    feed = db.query(InstagramFeed).filter(InstagramFeed.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed no encontrado")
    feed.is_rizoma = not feed.is_rizoma
    log_action(db, current_user.id, "instagram_feed_rizoma_toggled", request, "instagram_feeds", feed.id,
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
    feed = db.query(InstagramFeed).filter(InstagramFeed.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed no encontrado")
    feed.active = False
    log_action(db, current_user.id, "instagram_feed_deleted", request, "instagram_feeds", feed.id,
               {"display_name": feed.display_name, "feed_type": feed.feed_type})
    db.commit()


@router.get("/{feed_id}/mentions")
def get_feed_mentions(
    feed_id:   uuid.UUID,
    sentiment: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    q:         Optional[str] = Query(None, min_length=2),
    page:      int           = Query(1, ge=1),
    db:        Session       = Depends(get_db),
    _:         User          = Depends(get_current_user),
):
    feed = db.query(InstagramFeed).filter(InstagramFeed.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed no encontrado")
    if not feed.entity_id:
        return {"feed": _feed_to_dict(feed, db), "mentions": [], "total": 0, "page": page, "pages": 1}

    platform = db.query(SocialPlatform).filter(SocialPlatform.code == PLATFORM_CODE).first()

    qs = db.query(Mention).filter(Mention.entity_id == feed.entity_id)
    if platform:
        qs = qs.filter(Mention.platform_id == platform.id)
    if sentiment:
        qs = qs.filter(Mention.sentiment_label == sentiment)
    if date_from:
        qs = qs.filter(Mention.published_at >= datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc))
    if date_to:
        qs = qs.filter(Mention.published_at <= datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc))
    if q:
        qs = qs.filter(Mention.content.ilike(f"%{q}%"))

    total = qs.count()
    mentions_db = qs.order_by(Mention.published_at.desc().nullslast()).offset((page - 1) * 20).limit(20).all()

    def _m_dict(m: Mention) -> dict:
        return {
            "id":              str(m.id),
            "content":         m.content,
            "author_username": m.author_username,
            "url":             m.url,
            "published_at":    m.published_at.isoformat() if m.published_at else None,
            "sentiment_label": m.sentiment_label,
            "urgency_score":   float(m.urgency_score) if m.urgency_score is not None else 0,
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
