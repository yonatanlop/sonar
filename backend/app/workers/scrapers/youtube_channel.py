"""
YoutubeChannelScraper — busca videos dentro de los canales configurados en YouTube Explorer.

Complementa al YouTubeScraper global: este opera sobre canales específicos
(@jdoviedoar, etc.) con keywords asignadas por el usuario.
"""
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.mention import SocialPlatform
from app.models.youtube_channel import YoutubeChannel, YoutubeChannelKeyword
from app.workers.scrapers.base import save_mention

logger = logging.getLogger(__name__)

DAYS_BACK = 2
MAX_RESULTS_PER_KEYWORD = 25
DELAY = 1


class YoutubeChannelScraper:
    """Scraper para canales asignados en YouTube Explorer."""

    def __init__(self, db: Session):
        self.db = db
        if not settings.YOUTUBE_API_KEY:
            raise RuntimeError("YOUTUBE_API_KEY no configurada")
        self.yt = build("youtube", "v3", developerKey=settings.YOUTUBE_API_KEY)
        self.platform = db.query(SocialPlatform).filter(SocialPlatform.code == "youtube").first()
        if not self.platform:
            raise RuntimeError("Plataforma 'youtube' no encontrada en BD")

    def run(self) -> dict:
        channels = (
            self.db.query(YoutubeChannel)
            .filter(YoutubeChannel.active == True)
            .all()
        )
        total = 0
        for ch in channels:
            active_kws = [k for k in ch.keywords if k.active]
            if not active_kws:
                continue
            try:
                saved = self._scrape_channel(ch, active_kws)
                total += saved
                self.db.commit()
                logger.info(f"[YTChannels] @{ch.handle}: {saved} nuevas menciones")
            except HttpError as e:
                if e.resp.status == 403:
                    logger.error("[YTChannels] Cuota diaria agotada. Deteniendo.")
                    self.db.rollback()
                    break
                logger.warning(f"[YTChannels] HTTP error en @{ch.handle}: {e}")
                self.db.rollback()
            except Exception as e:
                logger.error(f"[YTChannels] Error en @{ch.handle}: {e}", exc_info=True)
                self.db.rollback()
        return {"scraped": total}

    def _scrape_channel(self, ch: YoutubeChannel, keywords: list) -> int:
        saved_total = 0
        published_after = (
            datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        from app.models.entity import Entity as _Entity
        _ent = self.db.query(_Entity).filter(_Entity.id == ch.entity_id).first()
        _country_code = _ent.country_code if _ent else None

        for kw in keywords:
            try:
                response = self.yt.search().list(
                    channelId=ch.channel_id,
                    q=kw.keyword,
                    part="snippet",
                    type="video",
                    maxResults=MAX_RESULTS_PER_KEYWORD,
                    publishedAfter=published_after,
                    order="date",
                ).execute()
            except HttpError:
                raise

            for item in response.get("items", []):
                vid_id = item["id"]["videoId"]
                sn = item["snippet"]
                title = sn.get("title", "")
                description = sn.get("description", "")
                channel_title = sn.get("channelTitle", "")
                channel_id_yt = sn.get("channelId", "")
                thumbs = sn.get("thumbnails", {})
                thumb_url = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url")

                published_at = None
                pub_str = sn.get("publishedAt")
                if pub_str:
                    try:
                        published_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                    except Exception:
                        pass

                mention = save_mention(
                    db=self.db,
                    platform_id=self.platform.id,
                    entity_id=ch.entity_id,
                    external_id=f"video_{vid_id}",
                    content=f"{title}\n\n{description}".strip(),
                    author_username=channel_title or channel_id_yt,
                    author_ext_id=channel_id_yt,
                    url=f"https://www.youtube.com/watch?v={vid_id}",
                    published_at=published_at,
                    language="es",
                    country_code=_country_code,
                    reach=0,
                    media_urls=json.dumps([thumb_url]) if thumb_url else None,
                )
                if mention:
                    saved_total += 1

            time.sleep(DELAY)

        return saved_total
