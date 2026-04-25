"""
YouTube Explorer — Monitoreo de canales de YouTube por keywords.

Permite asignar cuentas específicas de YouTube (@jdoviedoar) y buscar
dentro de su contenido publicado usando palabras clave.
"""
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_analyst
from app.core.config import settings
from app.database import get_db
from app.models.mention import Mention, SocialPlatform
from app.models.user import User
from app.models.youtube_channel import YoutubeChannel, YoutubeChannelKeyword
from app.workers.scrapers.base import save_mention

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/youtube-explorer", tags=["YouTube Explorer"])


# ── Schemas ──────────────────────────────────────────────────────

class ChannelCreate(BaseModel):
    handle: str
    entity_id: Optional[uuid.UUID] = None


class KeywordCreate(BaseModel):
    keyword: str


class SaveVideosRequest(BaseModel):
    video_ids: list[str]
    channel_id: int
    entity_id: Optional[uuid.UUID] = None


# ── Helpers ───────────────────────────────────────────────────────

def _normalize_handle(handle: str) -> str:
    handle = handle.strip()
    if "youtube.com/@" in handle:
        handle = handle.split("/@")[-1].split("/")[0].split("?")[0]
    elif "youtube.com/channel/" in handle:
        raise ValueError("Usa el @handle del canal, no el ID de canal")
    return handle.lstrip("@").strip()


def _resolve_channel(handle: str) -> dict:
    if not settings.YOUTUBE_API_KEY:
        raise HTTPException(status_code=503, detail="YOUTUBE_API_KEY no configurada")
    resp = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={"part": "snippet", "forHandle": handle, "key": settings.YOUTUBE_API_KEY},
        timeout=10,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=503, detail=f"Error YouTube API: {resp.status_code}")
    items = resp.json().get("items", [])
    if not items:
        raise HTTPException(status_code=404, detail=f"Canal '@{handle}' no encontrado en YouTube")
    snippet = items[0]["snippet"]
    thumbs = snippet.get("thumbnails", {})
    thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url")
    return {
        "channel_id":   items[0]["id"],
        "channel_name": snippet.get("title", handle),
        "thumbnail_url": thumb,
    }


def _fetch_video_stats(video_ids: list[str]) -> dict:
    if not video_ids or not settings.YOUTUBE_API_KEY:
        return {}
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "statistics,contentDetails", "id": ",".join(video_ids), "key": settings.YOUTUBE_API_KEY},
            timeout=10,
        )
        if resp.status_code != 200:
            return {}
        result = {}
        for item in resp.json().get("items", []):
            stats = item.get("statistics", {})
            dur_raw = item.get("contentDetails", {}).get("duration")
            result[item["id"]] = {
                "viewCount":    int(stats["viewCount"]) if stats.get("viewCount") else None,
                "commentCount": int(stats["commentCount"]) if stats.get("commentCount") else None,
                "duration":     _fmt_duration(dur_raw),
            }
        return result
    except Exception:
        return {}


def _fmt_duration(iso: Optional[str]) -> Optional[str]:
    if not iso:
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return None
    h, mi, s = int(m.group(1) or 0), int(m.group(2) or 0), int(m.group(3) or 0)
    return f"{h}:{mi:02d}:{s:02d}" if h else f"{mi}:{s:02d}"


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _channel_dict(ch: YoutubeChannel, db: Session) -> dict:
    yt = db.query(SocialPlatform).filter(SocialPlatform.code == "youtube").first()
    mention_count = 0
    if yt and ch.entity_id:
        mention_count = db.query(func.count(Mention.id)).filter(
            Mention.entity_id == ch.entity_id,
            Mention.platform_id == yt.id,
        ).scalar() or 0
    return {
        "id":            ch.id,
        "handle":        f"@{ch.handle}",
        "channel_id":    ch.channel_id,
        "channel_name":  ch.channel_name,
        "thumbnail_url": ch.thumbnail_url,
        "active":        ch.active,
        "entity_id":     ch.entity_id,
        "keyword_count": len([k for k in ch.keywords if k.active]),
        "mention_count": mention_count,
    }


# ── Canales — CRUD ────────────────────────────────────────────────

@router.get("/channels")
def list_channels(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    channels = db.query(YoutubeChannel).order_by(YoutubeChannel.created_at).all()
    return [_channel_dict(ch, db) for ch in channels]


@router.post("/channels", status_code=201)
def create_channel(data: ChannelCreate, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    try:
        handle = _normalize_handle(data.handle)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not handle:
        raise HTTPException(status_code=422, detail="El handle no puede estar vacío")

    existing = db.query(YoutubeChannel).filter(YoutubeChannel.handle == handle).first()
    if existing:
        if not existing.active:
            existing.active = True
            db.commit()
            return _channel_dict(existing, db)
        raise HTTPException(status_code=409, detail=f"El canal '@{handle}' ya está registrado")

    resolved = _resolve_channel(handle)

    dup_id = db.query(YoutubeChannel).filter(YoutubeChannel.channel_id == resolved["channel_id"]).first()
    if dup_id:
        raise HTTPException(status_code=409, detail=f"Este canal ya existe como '@{dup_id.handle}'")

    ch = YoutubeChannel(
        handle=handle,
        channel_id=resolved["channel_id"],
        channel_name=resolved["channel_name"],
        thumbnail_url=resolved["thumbnail_url"],
        active=True,
        entity_id=data.entity_id,
        created_by=user.id,
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return _channel_dict(ch, db)


@router.patch("/channels/{channel_id}/toggle")
def toggle_channel(channel_id: int, db: Session = Depends(get_db), _: User = Depends(require_analyst)):
    ch = db.query(YoutubeChannel).filter(YoutubeChannel.id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    ch.active = not ch.active
    db.commit()
    return _channel_dict(ch, db)


@router.delete("/channels/{channel_id}", status_code=204)
def delete_channel(channel_id: int, db: Session = Depends(get_db), _: User = Depends(require_analyst)):
    ch = db.query(YoutubeChannel).filter(YoutubeChannel.id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    db.delete(ch)
    db.commit()


# ── Keywords ──────────────────────────────────────────────────────

@router.get("/channels/{channel_id}/keywords")
def list_keywords(channel_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    ch = db.query(YoutubeChannel).filter(YoutubeChannel.id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    return [{"id": k.id, "keyword": k.keyword, "active": k.active} for k in ch.keywords]


@router.post("/channels/{channel_id}/keywords", status_code=201)
def add_keyword(channel_id: int, data: KeywordCreate, db: Session = Depends(get_db), _: User = Depends(require_analyst)):
    ch = db.query(YoutubeChannel).filter(YoutubeChannel.id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    kw_text = data.keyword.strip()
    if not kw_text:
        raise HTTPException(status_code=422, detail="La keyword no puede estar vacía")
    existing = db.query(YoutubeChannelKeyword).filter(
        YoutubeChannelKeyword.channel_id == channel_id,
        YoutubeChannelKeyword.keyword == kw_text,
    ).first()
    if existing:
        if not existing.active:
            existing.active = True
            db.commit()
        return {"id": existing.id, "keyword": existing.keyword, "active": existing.active}
    kw = YoutubeChannelKeyword(channel_id=channel_id, keyword=kw_text)
    db.add(kw)
    db.commit()
    db.refresh(kw)
    return {"id": kw.id, "keyword": kw.keyword, "active": kw.active}


@router.delete("/channels/{channel_id}/keywords/{keyword_id}", status_code=204)
def delete_keyword(channel_id: int, keyword_id: int, db: Session = Depends(get_db), _: User = Depends(require_analyst)):
    kw = db.query(YoutubeChannelKeyword).filter(
        YoutubeChannelKeyword.id == keyword_id,
        YoutubeChannelKeyword.channel_id == channel_id,
    ).first()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword no encontrada")
    db.delete(kw)
    db.commit()


# ── Búsqueda on-demand ────────────────────────────────────────────

@router.get("/channels/{channel_id}/search")
def search_channel(
    channel_id:  int,
    keyword:     Optional[str] = Query(None, description="Buscar dentro del canal"),
    days_back:   int           = Query(7,  ge=1, le=90),
    max_results: int           = Query(20, ge=1, le=50),
    db:          Session       = Depends(get_db),
    _:           User          = Depends(get_current_user),
):
    ch = db.query(YoutubeChannel).filter(YoutubeChannel.id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    if not settings.YOUTUBE_API_KEY:
        raise HTTPException(status_code=503, detail="YOUTUBE_API_KEY no configurada")

    published_after = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "part": "snippet",
        "channelId": ch.channel_id,
        "type": "video",
        "maxResults": max_results,
        "publishedAfter": published_after,
        "order": "date",
        "key": settings.YOUTUBE_API_KEY,
    }
    if keyword:
        params["q"] = keyword

    resp = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, timeout=15)
    if resp.status_code == 403:
        raise HTTPException(status_code=503, detail="Cuota diaria de YouTube API agotada")
    if resp.status_code != 200:
        raise HTTPException(status_code=503, detail=f"Error YouTube Search API: {resp.status_code}")

    items = resp.json().get("items", [])
    if not items:
        return []

    video_ids = [item["id"]["videoId"] for item in items]
    stats_map = _fetch_video_stats(video_ids)

    yt_platform = db.query(SocialPlatform).filter(SocialPlatform.code == "youtube").first()

    results = []
    for item in items:
        vid_id = item["id"]["videoId"]
        sn = item["snippet"]
        thumbs = sn.get("thumbnails", {})
        thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
        stats = stats_map.get(vid_id, {})

        in_db = False
        mention_id = None
        sentiment_label = None
        if yt_platform:
            m = db.query(Mention).filter(
                Mention.platform_id == yt_platform.id,
                Mention.external_id == f"video_{vid_id}",
            ).first()
            if m:
                in_db = True
                mention_id = str(m.id)
                sentiment_label = m.sentiment_label

        results.append({
            "video_id":      vid_id,
            "title":         sn.get("title", ""),
            "description":   sn.get("description", "")[:300],
            "channel_name":  sn.get("channelTitle", ""),
            "thumbnail_url": thumb,
            "published_at":  sn.get("publishedAt", ""),
            "view_count":    stats.get("viewCount"),
            "comment_count": stats.get("commentCount"),
            "duration":      stats.get("duration"),
            "url":           f"https://www.youtube.com/watch?v={vid_id}",
            "in_db":         in_db,
            "mention_id":    mention_id,
            "sentiment_label": sentiment_label,
        })

    return results


# ── Guardar videos como menciones ────────────────────────────────

@router.post("/save")
def save_videos(data: SaveVideosRequest, db: Session = Depends(get_db), _: User = Depends(require_analyst)):
    if not settings.YOUTUBE_API_KEY:
        raise HTTPException(status_code=503, detail="YOUTUBE_API_KEY no configurada")
    if not data.video_ids:
        raise HTTPException(status_code=422, detail="video_ids no puede estar vacío")

    ch = db.query(YoutubeChannel).filter(YoutubeChannel.id == data.channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="Canal no encontrado")

    yt_platform = db.query(SocialPlatform).filter(SocialPlatform.code == "youtube").first()
    if not yt_platform:
        raise HTTPException(status_code=500, detail="Plataforma YouTube no encontrada en BD")

    entity_id = data.entity_id or ch.entity_id

    resp = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "snippet,statistics", "id": ",".join(data.video_ids[:50]), "key": settings.YOUTUBE_API_KEY},
        timeout=15,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=503, detail="Error al obtener detalles del video de YouTube API")

    video_items = {item["id"]: item for item in resp.json().get("items", [])}
    saved_count = 0
    already_count = 0

    for vid_id in data.video_ids:
        item = video_items.get(vid_id)
        if not item:
            continue
        sn = item.get("snippet", {})
        title = sn.get("title", "")
        description = sn.get("description", "")
        channel_title = sn.get("channelTitle", "")
        channel_id_yt = sn.get("channelId", "")
        thumbs = sn.get("thumbnails", {})
        thumb_url = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url")

        content = f"{title}\n\n{description}".strip()
        media_urls = json.dumps([thumb_url]) if thumb_url else None

        mention = save_mention(
            db=db,
            platform_id=yt_platform.id,
            entity_id=entity_id,
            external_id=f"video_{vid_id}",
            content=content,
            author_username=channel_title or channel_id_yt,
            author_ext_id=channel_id_yt,
            url=f"https://www.youtube.com/watch?v={vid_id}",
            published_at=_parse_dt(sn.get("publishedAt")),
            language="es",
            reach=0,
            media_urls=media_urls,
        )
        if mention:
            saved_count += 1
        else:
            already_count += 1

    db.commit()
    return {"saved": saved_count, "already_existed": already_count}
