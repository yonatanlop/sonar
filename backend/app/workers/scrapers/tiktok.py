"""
TikTok scraper — búsqueda de videos por keyword y entidad.

Requiere:
  - TikTokApi >= 6.0.0  (pip install TikTokApi)
  - Playwright + Chromium (playwright install chromium)
  - TIKTOK_MS_TOKEN en .env  (cookie msToken de tiktok.com)

Cómo obtener ms_token:
  1. Abrir tiktok.com en Chrome/Firefox
  2. DevTools → Application → Cookies → tiktok.com → msToken
  3. Pegar el valor en TIKTOK_MS_TOKEN=...
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entity import Entity, Keyword
from app.workers.scrapers.base import BaseScraper, keyword_matches_text, save_mention

logger = logging.getLogger(__name__)


class TikTokScraper(BaseScraper):
    platform_code = "tiktok"

    def __init__(self, db: Session):
        super().__init__(db)
        if not settings.TIKTOK_MS_TOKEN:
            raise RuntimeError(
                "TIKTOK_MS_TOKEN no configurado. "
                "Exporta el valor de la cookie msToken desde tiktok.com."
            )

    def scrape_entity(self, entity: Entity, keywords: list[Keyword]) -> int:
        return asyncio.run(self._scrape_entity_async(entity, keywords))

    async def _scrape_entity_async(self, entity: Entity, keywords: list[Keyword]) -> int:
        from TikTokApi import TikTokApi  # import diferido — solo en el worker local

        since = datetime.now(tz=timezone.utc) - timedelta(days=settings.TIKTOK_LOOKBACK_DAYS)
        saved = 0

        try:
            async with TikTokApi() as api:
                await api.create_sessions(
                    ms_tokens=[settings.TIKTOK_MS_TOKEN],
                    num_sessions=1,
                    sleep_after=3,
                    headless=True,
                    override_browser_args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--single-process",
                    ],
                    timeout=60000,
                )
                seen_terms: set[str] = set()
                for kw in sorted(keywords, key=lambda k: k.weight, reverse=True):
                    term = (
                        (kw.keyword_expression or "").strip()
                        or kw.keyword.strip()
                    )
                    if term.lower() in seen_terms:
                        continue
                    seen_terms.add(term.lower())

                    try:
                        count = await self._search_term(api, term, entity, kw, since)
                        saved += count
                        logger.info(f"[TikTok] '{term}' → {count} guardados")
                    except Exception as e:
                        logger.warning(f"[TikTok] Error buscando '{term}': {e}")

        except Exception as e:
            logger.error(f"[TikTok] Error inicializando sesión: {e}", exc_info=True)
            raise

        return saved

    async def _search_term(
        self,
        api,
        term: str,
        entity: Entity,
        keyword_obj,
        since: datetime,
    ) -> int:
        saved = 0
        async for video in api.search.search_type(
            term, "item", count=settings.TIKTOK_MAX_RESULTS
        ):
            saved += self._save_video(video, entity, keyword_obj, since)
        return saved

    async def _search_hashtag(self, api, hashtag: str, entity: Entity, since: datetime) -> int:
        """Videos de un hashtag (TikTok Explorer)."""
        saved = 0
        tag = api.hashtag(name=hashtag.lstrip("#"))
        async for video in tag.videos(count=settings.TIKTOK_MAX_RESULTS):
            saved += self._save_video(video, entity, None, since)
        return saved

    async def _search_user(self, api, username: str, entity: Entity, since: datetime) -> int:
        """Videos de un creador/usuario (TikTok Explorer)."""
        saved = 0
        user = api.user(username=username.lstrip("@"))
        async for video in user.videos(count=settings.TIKTOK_MAX_RESULTS):
            saved += self._save_video(video, entity, None, since)
        return saved

    def _save_video(self, video, entity: Entity, keyword_obj, since: datetime) -> int:
        """Guarda un video de TikTok como mención. Retorna 1 si se guardó, 0 si no."""
        try:
            data = video.as_dict

            create_ts = data.get("createTime")
            if not create_ts:
                return 0
            published_at = datetime.fromtimestamp(int(create_ts), tz=timezone.utc)
            if published_at < since:
                return 0

            caption = (data.get("desc") or "").strip()
            if not caption:
                return 0

            # Solo filtra por keyword cuando viene de búsqueda por entidad
            if keyword_obj is not None and not keyword_matches_text(caption, keyword_obj):
                return 0

            author = data.get("author") or {}
            username = author.get("uniqueId") or author.get("nickname") or "unknown"
            author_id = str(author.get("id") or "")
            video_id = str(data.get("id") or getattr(video, "id", ""))
            url = f"https://www.tiktok.com/@{username}/video/{video_id}"

            stats = data.get("stats") or {}
            reach = (
                int(stats.get("diggCount") or 0)
                + int(stats.get("commentCount") or 0)
                + int(stats.get("shareCount") or 0)
            )

            media_url = None
            video_meta = data.get("video") or {}
            cover = video_meta.get("cover") or video_meta.get("originCover")
            if cover:
                media_url = json.dumps([cover])

            mention = save_mention(
                db=self.db,
                platform_id=self.platform.id,
                entity_id=entity.id,
                external_id=f"tt_{video_id}",
                content=caption,
                author_username=username,
                author_ext_id=author_id,
                url=url,
                published_at=published_at,
                language="es",
                country_code=entity.country_code,
                reach=reach,
                matched_keywords=[keyword_obj] if keyword_obj else None,
                media_urls=media_url,
            )
            return 1 if mention else 0

        except Exception as e:
            logger.warning(f"[TikTok] Error procesando video: {e}")
            return 0

    async def _scrape_feeds_async(self, db: Session) -> dict:
        """TikTok Explorer — recolecta feeds por keyword, hashtag o creador."""
        from TikTokApi import TikTokApi
        from app.models.entity import Entity as _Entity
        from app.models.tiktok_feed import TiktokFeed

        feeds = db.query(TiktokFeed).filter(TiktokFeed.active == True).all()
        if not feeds:
            return {"feeds": 0, "saved": 0}

        since = datetime.now(tz=timezone.utc) - timedelta(days=settings.TIKTOK_LOOKBACK_DAYS)
        total_saved = 0

        async with TikTokApi() as api:
            await api.create_sessions(
                ms_tokens=[settings.TIKTOK_MS_TOKEN],
                num_sessions=1,
                sleep_after=3,
                headless=True,
                override_browser_args=[
                    "--no-sandbox", "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage", "--disable-gpu", "--single-process",
                ],
                timeout=60000,
            )
            for feed in feeds:
                if not feed.entity_id:
                    continue
                entity = db.query(_Entity).filter(_Entity.id == feed.entity_id).first()
                if not entity:
                    continue
                try:
                    if feed.feed_type == "hashtag":
                        saved = await self._search_hashtag(api, feed.term, entity, since)
                    elif feed.feed_type == "creator":
                        saved = await self._search_user(api, feed.term, entity, since)
                    else:  # keyword
                        saved = await self._search_term(api, feed.term, entity, None, since)
                    total_saved += saved
                    logger.info(f"[TikTokExplorer] {feed.display_name}: {saved} nuevos videos")
                except Exception as e:
                    logger.warning(f"[TikTokExplorer] Error en {feed.display_name}: {e}")

        return {"feeds": len(feeds), "saved": total_saved}


def scrape_feeds(db: Session) -> dict:
    """Entry point sync para la task de Celery (TikTok Explorer)."""
    scraper = TikTokScraper(db)
    return asyncio.run(scraper._scrape_feeds_async(db))
