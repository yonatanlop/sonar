"""
Rizoma — Vista unificada de cuentas hostiles conocidas.
Agrega las menciones recientes de todos los feeds/canales marcados como Rizoma.
"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.mention import Mention
from app.models.twitter_feed import TwitterFeed
from app.models.youtube_channel import YoutubeChannel

router = APIRouter(prefix="/rizoma", tags=["Rizoma"])

PAGE_SIZE = 30


@router.get("/sources")
def list_rizoma_sources(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Lista las cuentas marcadas como Rizoma (Twitter + YouTube)."""
    twitter = db.query(TwitterFeed).filter(TwitterFeed.is_rizoma == True).order_by(TwitterFeed.display_name).all()
    youtube = db.query(YoutubeChannel).filter(YoutubeChannel.is_rizoma == True).order_by(YoutubeChannel.channel_name).all()

    return {
        "twitter": [{"id": str(f.id), "name": f.display_name, "active": f.active} for f in twitter],
        "youtube": [{"id": ch.id, "name": ch.channel_name, "handle": f"@{ch.handle}", "active": ch.active} for ch in youtube],
    }


@router.get("/feed")
def get_rizoma_feed(
    page: int = Query(1, ge=1),
    platform: str = Query(None, description="twitter | youtube"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Menciones recientes de todas las cuentas Rizoma.
    No filtra por keyword — muestra TODO lo que publicaron.
    """
    rizoma_twitter = db.query(TwitterFeed).filter(
        TwitterFeed.is_rizoma == True, TwitterFeed.active == True,
    ).all()
    rizoma_youtube = db.query(YoutubeChannel).filter(
        YoutubeChannel.is_rizoma == True, YoutubeChannel.active == True,
    ).all()

    entity_map: dict[str, dict] = {}
    for f in rizoma_twitter:
        if f.entity_id:
            entity_map[str(f.entity_id)] = {"name": f.display_name, "type": "twitter"}
    for ch in rizoma_youtube:
        if ch.entity_id:
            entity_map[str(ch.entity_id)] = {"name": ch.channel_name, "type": "youtube"}

    if platform == "twitter":
        entity_map = {k: v for k, v in entity_map.items() if v["type"] == "twitter"}
    elif platform == "youtube":
        entity_map = {k: v for k, v in entity_map.items() if v["type"] == "youtube"}

    entity_ids = [uuid.UUID(eid) for eid in entity_map]

    if not entity_ids:
        return {"items": [], "total": 0, "page": page, "pages": 1}

    q = db.query(Mention).filter(Mention.entity_id.in_(entity_ids))
    total = q.count()
    mentions = (
        q.order_by(Mention.collected_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .all()
    )

    items = []
    for m in mentions:
        source = entity_map.get(str(m.entity_id), {})
        items.append({
            "id":              str(m.id),
            "content":         m.content,
            "author_username": m.author_username,
            "platform_code":   m.platform.code if m.platform else None,
            "url":             m.url,
            "published_at":    m.published_at.isoformat() if m.published_at else None,
            "collected_at":    m.collected_at.isoformat() if m.collected_at else None,
            "sentiment_label": m.sentiment_label,
            "urgency_score":   float(m.urgency_score) if m.urgency_score is not None else None,
            "is_hate_speech":  m.is_hate_speech,
            "source_name":     source.get("name", "—"),
            "source_type":     source.get("type", "unknown"),
        })

    return {
        "items":  items,
        "total":  total,
        "page":   page,
        "pages":  max(1, -(-total // PAGE_SIZE)),
    }
