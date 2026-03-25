"""
YouTubeScraper — usa YouTube Data API v3.
Gratuita con cuota de 10,000 unidades/día.

Costo por operación:
  search.list      = 100 unidades  (búsqueda de videos)
  commentThreads   = 1  unidad     (comentarios de un video)
  videos.list      = 1  unidad     (metadata de un video)

Estrategia conservadora por defecto:
  - Máx 5 búsquedas/entidad → 500 unidades
  - Máx 20 comentarios/video → 20 unidades
  - Con 10 entidades activas: ~5,200 unidades/ciclo (seguro)

Credenciales necesarias (.env):
  YOUTUBE_API_KEY — obtenida en console.cloud.google.com (gratuita)
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entity import Entity, Keyword
from app.workers.scrapers.base import (
    BaseScraper, build_search_terms, save_mention, upsert_account_profile,
)

logger = logging.getLogger(__name__)

MAX_VIDEOS_PER_SEARCH   = 25
MAX_COMMENTS_PER_VIDEO  = 20
PUBLISHED_AFTER_HOURS   = 48   # solo videos de las últimas 48h
DELAY_BETWEEN_CALLS     = 1    # segundo entre llamadas API


class YouTubeScraper(BaseScraper):
    platform_code = "youtube"

    def __init__(self, db: Session):
        super().__init__(db)
        if not settings.YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY no configurada en .env")
        self.yt = build("youtube", "v3", developerKey=settings.YOUTUBE_API_KEY)

    def scrape_entity(self, entity: Entity, keywords: list[Keyword]) -> int:
        saved_total = 0
        search_terms = build_search_terms(entity, keywords)

        # Limitar a los 5 términos de mayor peso para conservar cuota
        for term, keyword_obj in search_terms[:5]:
            try:
                saved = self._search_videos(term, entity, keyword_obj)
                saved_total += saved
                time.sleep(DELAY_BETWEEN_CALLS)
            except HttpError as e:
                if e.resp.status == 403:
                    logger.error("[YouTube] Cuota diaria agotada. Deteniendo scraping.")
                    break
                logger.warning(f"[YouTube] HTTP error buscando '{term}': {e}")
            except Exception as e:
                logger.error(f"[YouTube] Error inesperado buscando '{term}': {e}")

        return saved_total

    def _search_videos(self, term: str, entity: Entity, keyword_obj: Keyword) -> int:
        saved = 0

        # Calcular fecha de publicación mínima
        from datetime import timedelta
        published_after = (
            datetime.now(timezone.utc) - timedelta(hours=PUBLISHED_AFTER_HOURS)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            response = self.yt.search().list(
                q=term,
                part="snippet",
                type="video",
                maxResults=MAX_VIDEOS_PER_SEARCH,
                publishedAfter=published_after,
                relevanceLanguage="es",
                order="date",
            ).execute()
        except HttpError:
            raise

        for item in response.get("items", []):
            video_id = item["id"]["videoId"]
            snippet  = item["snippet"]

            channel_id    = snippet.get("channelId", "")
            channel_title = snippet.get("channelTitle", "")
            title         = snippet.get("title", "")
            description   = snippet.get("description", "")

            # Guardar canal como account_profile
            if channel_id:
                upsert_account_profile(
                    db=self.db,
                    platform_id=self.platform.id,
                    username=channel_title or channel_id,
                    external_user_id=channel_id,
                )

            # Guardar el video como mención (título + descripción)
            content = f"{title}\n\n{description}".strip()
            published_at = self._parse_dt(snippet.get("publishedAt"))

            mention = save_mention(
                db=self.db,
                platform_id=self.platform.id,
                entity_id=entity.id,
                external_id=f"video_{video_id}",
                content=content,
                author_username=channel_title or channel_id,
                author_ext_id=channel_id,
                url=f"https://www.youtube.com/watch?v={video_id}",
                published_at=published_at,
                language="es",
                reach=0,  # se actualiza con video stats si se necesita más precisión
                matched_keywords=[keyword_obj],
            )
            if mention:
                saved += 1

            # Comentarios del video
            saved += self._save_comments(video_id, entity, keyword_obj, term)
            time.sleep(DELAY_BETWEEN_CALLS)

        return saved

    def _save_comments(self, video_id: str, entity: Entity,
                       keyword_obj: Keyword, term: str) -> int:
        saved = 0
        try:
            response = self.yt.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=MAX_COMMENTS_PER_VIDEO,
                order="relevance",
                textFormat="plainText",
            ).execute()
        except HttpError as e:
            # Comentarios desactivados en el video
            if e.resp.status in (403, 404):
                return 0
            raise

        for item in response.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            comment_text = top.get("textDisplay", "")

            if not comment_text:
                continue

            author_name      = top.get("authorDisplayName", "")
            author_channel   = top.get("authorChannelId", {}).get("value", "")
            like_count       = top.get("likeCount", 0)
            published_at     = self._parse_dt(top.get("publishedAt"))
            comment_id       = item["id"]

            if author_channel:
                upsert_account_profile(
                    db=self.db,
                    platform_id=self.platform.id,
                    username=author_name or author_channel,
                    external_user_id=author_channel,
                )

            mention = save_mention(
                db=self.db,
                platform_id=self.platform.id,
                entity_id=entity.id,
                external_id=f"comment_{comment_id}",
                content=comment_text,
                author_username=author_name or author_channel,
                author_ext_id=author_channel or None,
                url=f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
                published_at=published_at,
                language="es",
                reach=like_count,
                matched_keywords=[keyword_obj],
            )
            if mention:
                saved += 1

        return saved

    @staticmethod
    def _parse_dt(dt_str: Optional[str]) -> Optional[datetime]:
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except Exception:
            return None
