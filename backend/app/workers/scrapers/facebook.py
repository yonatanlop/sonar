"""
Scraper de Facebook para SONAR.
Usa facebook-scraper con cookies de sesión exportadas desde una cuenta real.
El proceso de obtención de cookies es idéntico al de Twitter:
  1. Instalar Cookie-Editor en Chrome
  2. Ir a facebook.com (logueado)
  3. Cookie-Editor → Export → guardar como fb_cookies.json en storage/
  4. docker cp storage/fb_cookies.json sonar_worker:/app/storage/fb_cookies.json
"""
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.entity import Entity, Keyword
from app.workers.scrapers.base import BaseScraper, build_search_terms, save_mention, upsert_account_profile

logger = logging.getLogger(__name__)

DELAY_BETWEEN_SEARCHES = 6   # segundos entre búsquedas (Facebook detecta requests rápidos)
PAGES_PER_SEARCH       = 2   # "páginas" de resultados por keyword (~20 posts/página)


def _load_cookies(cookies_file: str) -> Optional[dict]:
    """
    Carga cookies desde archivo JSON (formato Cookie-Editor: array de objetos).
    Convierte a dict {name: value} que acepta facebook-scraper.
    Retorna None si el archivo no existe.
    """
    path = Path(cookies_file)
    if not path.exists():
        return None
    try:
        with open(path) as f:
            raw = json.load(f)
        # Cookie-Editor exporta lista de objetos con campos "name" y "value"
        if isinstance(raw, list):
            return {c["name"]: c["value"] for c in raw if "name" in c and "value" in c}
        # Ya es dict (formato simplificado)
        if isinstance(raw, dict):
            return raw
    except Exception as e:
        logger.error(f"[Facebook] Error leyendo cookies desde {cookies_file}: {e}")
    return None


class FacebookScraper(BaseScraper):
    """
    Scraper de Facebook usando facebook-scraper con cookies de sesión.
    Busca posts públicos por keyword para cada entidad activa.
    """
    platform_code = "facebook"

    def __init__(self, db: Session):
        super().__init__(db)
        from app.core.config import settings
        self._cookies = _load_cookies(settings.FB_COOKIES_FILE)

        if not self._cookies:
            raise RuntimeError(
                f"Facebook: archivo de cookies no encontrado en '{settings.FB_COOKIES_FILE}'. "
                "Exporta las cookies desde facebook.com con Cookie-Editor y cópialas al contenedor:\n"
                "  docker cp storage/fb_cookies.json sonar_worker:/app/storage/fb_cookies.json"
            )

    def scrape_entity(self, entity: Entity, keywords: list[Keyword]) -> int:
        from app.core.config import settings
        saved_total  = 0
        since        = datetime.now(timezone.utc) - timedelta(days=settings.FB_LOOKBACK_DAYS)
        search_terms = build_search_terms(entity, keywords)

        for term, keyword_obj in search_terms:
            try:
                saved = self._search_keyword(term, entity, keyword_obj, since)
                saved_total += saved
                logger.debug(f"[Facebook] '{term}' → {saved} nuevos posts para {entity.name}")
            except RuntimeError:
                raise   # propaga errores de configuración (cookies inválidas)
            except Exception as e:
                logger.warning(f"[Facebook] Error buscando '{term}': {e}")

            time.sleep(DELAY_BETWEEN_SEARCHES)

        return saved_total

    def _search_keyword(
        self,
        term: str,
        entity: Entity,
        keyword_obj: Keyword,
        since: datetime,
    ) -> int:
        try:
            import facebook_scraper as fb
        except ImportError:
            raise RuntimeError("facebook-scraper no instalado. Ejecuta: pip install facebook-scraper>=0.2.59")

        saved = 0

        try:
            posts_gen = fb.search_posts(
                term,
                pages=PAGES_PER_SEARCH,
                cookies=self._cookies,
                options={"allow_extra_requests": False},  # sin requests adicionales
            )
        except Exception as e:
            logger.warning(f"[Facebook] search_posts('{term}') falló: {e}")
            return 0

        for post in posts_gen:
            # Filtrar por fecha
            post_time = post.get("time")
            if post_time:
                if isinstance(post_time, datetime):
                    pub_at = post_time if post_time.tzinfo else post_time.replace(tzinfo=timezone.utc)
                else:
                    pub_at = None
                if pub_at and pub_at < since:
                    continue
            else:
                pub_at = None

            post_id  = str(post.get("post_id") or post.get("post_url") or "")
            if not post_id:
                continue

            text     = post.get("text") or post.get("post_text") or ""
            post_url = post.get("post_url") or post.get("link") or ""
            username = post.get("username") or post.get("user_id") or ""
            user_id  = str(post.get("user_id") or "")
            likes    = int(post.get("likes") or 0)
            comments = int(post.get("comments") or 0)
            shares   = int(post.get("shares") or 0)
            reach    = likes + comments + shares

            # Imágenes adjuntas al post
            images   = post.get("images") or []
            media_urls = json.dumps(images[:5]) if images else None   # máximo 5 imágenes

            # Perfil del autor
            if username:
                upsert_account_profile(
                    db=self.db,
                    platform_id=self.platform.id,
                    username=str(username),
                    external_user_id=user_id or None,
                )

            mention = save_mention(
                db=self.db,
                platform_id=self.platform.id,
                entity_id=entity.id,
                external_id=f"fb_{post_id}",
                content=text or "[Post de Facebook sin texto]",
                author_username=str(username) if username else None,
                author_ext_id=user_id or None,
                url=str(post_url) if post_url else None,
                published_at=pub_at,
                country_code=entity.country_code,
                reach=reach,
                matched_keywords=[keyword_obj],
                media_urls=media_urls,
            )
            if mention:
                saved += 1

        return saved
