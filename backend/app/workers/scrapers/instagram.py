"""
Scraper de Instagram para SONAR.
Usa instagrapi con pool de cuentas rotatorio para buscar posts por hashtag/keyword.
Requiere al menos una cuenta configurada en .env (IG_ACCOUNT_1_USERNAME/PASSWORD).
"""
import json
import logging
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.entity import Entity, Keyword
from app.workers.scrapers.base import BaseScraper, build_search_terms, save_mention, upsert_account_profile

logger = logging.getLogger(__name__)

DELAY_BETWEEN_SEARCHES = 4   # segundos entre búsquedas (evita bloqueos)
MAX_POSTS_PER_HASHTAG  = 30  # posts por hashtag por ciclo
ROTATE_AFTER_REQUESTS  = 100 # cambiar de cuenta cada N búsquedas


def _normalize_hashtag(term: str) -> str:
    """Convierte un keyword a hashtag válido: sin tildes, sin espacios, sin símbolos."""
    # Quitar tildes
    nfkd = unicodedata.normalize("NFKD", term)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Quitar todo lo que no sea alfanumérico
    clean = re.sub(r"[^a-zA-Z0-9]", "", ascii_text)
    return clean.lower()


class InstagramScraper(BaseScraper):
    """
    Scraper de Instagram usando instagrapi.
    Busca posts recientes por hashtag correspondiente a cada keyword.
    """
    platform_code = "instagram"

    def __init__(self, db: Session):
        super().__init__(db)
        self._client = None
        self._accounts = self._load_accounts()
        self._current_account_idx = 0
        self._request_count = 0

        if not self._accounts:
            raise RuntimeError(
                "Instagram: no hay cuentas configuradas. "
                "Agrega IG_ACCOUNT_1_USERNAME y IG_ACCOUNT_1_PASSWORD en .env"
            )

    def _load_accounts(self) -> list[dict]:
        # Primero intentar leer desde la base de datos
        try:
            from app.database import SessionLocal
            from app.models.mention import InstagramAccount
            db = SessionLocal()
            try:
                rows = db.query(InstagramAccount).filter(InstagramAccount.active == True).all()
                if rows:
                    return [{"username": a.username, "password": a.password} for a in rows]
            finally:
                db.close()
        except Exception as exc:
            logger.warning(f"[Instagram] No se pudo leer cuentas desde DB, usando .env: {exc}")

        # Fallback a variables de entorno
        from app.core.config import settings
        accounts = []
        for i in range(1, 4):
            user = getattr(settings, f"IG_ACCOUNT_{i}_USERNAME", "")
            pwd  = getattr(settings, f"IG_ACCOUNT_{i}_PASSWORD", "")
            if user and pwd:
                accounts.append({"username": user, "password": pwd})
        return accounts

    def _get_client(self):
        """Retorna cliente instagrapi autenticado. Rota cuenta si supera el límite."""
        try:
            from instagrapi import Client
        except ImportError:
            raise RuntimeError("instagrapi no instalado. Ejecuta: pip install instagrapi>=2.0.0")

        if self._client is None or self._request_count >= ROTATE_AFTER_REQUESTS:
            if self._request_count >= ROTATE_AFTER_REQUESTS:
                self._current_account_idx = (self._current_account_idx + 1) % len(self._accounts)
                self._request_count = 0
                logger.info(f"[Instagram] Rotando cuenta → idx {self._current_account_idx}")

            account = self._accounts[self._current_account_idx]
            client = Client()
            client.delay_range = [2, 5]   # delays aleatorios en requests internos
            try:
                client.login(account["username"], account["password"])
                logger.info(f"[Instagram] Login OK con @{account['username']}")
            except Exception as e:
                raise RuntimeError(f"Instagram login fallido para @{account['username']}: {e}")
            self._client = client

        return self._client

    def scrape_entity(self, entity: Entity, keywords: list[Keyword]) -> int:
        from app.core.config import settings
        saved_total = 0
        since = datetime.now(timezone.utc) - timedelta(days=settings.IG_LOOKBACK_DAYS)
        search_terms = build_search_terms(entity, keywords)

        for term, keyword_obj in search_terms:
            hashtag = _normalize_hashtag(term)
            if not hashtag:
                continue

            try:
                saved = self._search_hashtag(hashtag, entity, keyword_obj, since)
                saved_total += saved
                self._request_count += 1
                logger.debug(f"[Instagram] #{hashtag} → {saved} nuevos posts para {entity.name}")
            except RuntimeError:
                raise   # propaga errores de configuración
            except Exception as e:
                logger.warning(f"[Instagram] Error en #{hashtag}: {e}")

            time.sleep(DELAY_BETWEEN_SEARCHES)

        return saved_total

    def _search_hashtag(
        self,
        hashtag: str,
        entity: Entity,
        keyword_obj: Keyword,
        since: datetime,
    ) -> int:
        client = self._get_client()
        saved = 0

        try:
            medias = client.hashtag_medias_recent(hashtag, amount=MAX_POSTS_PER_HASHTAG)
        except Exception as e:
            logger.warning(f"[Instagram] hashtag_medias_recent(#{hashtag}) falló: {e}")
            return 0

        for media in medias:
            # Filtrar por fecha
            taken_at = getattr(media, "taken_at", None)
            if taken_at:
                if taken_at.tzinfo is None:
                    taken_at = taken_at.replace(tzinfo=timezone.utc)
                if taken_at < since:
                    continue

            caption     = getattr(media, "caption_text", "") or ""
            media_pk    = str(getattr(media, "pk", ""))
            user        = getattr(media, "user", None)
            username    = getattr(user, "username", None) if user else None
            user_id     = str(getattr(user, "pk", "")) if user else None
            like_count  = getattr(media, "like_count", 0) or 0
            comment_cnt = getattr(media, "comment_count", 0) or 0
            reach       = like_count + comment_cnt
            media_type  = getattr(media, "media_type", 1)   # 1=foto, 2=video, 8=álbum

            # URL del post
            code = getattr(media, "code", media_pk)
            url  = f"https://www.instagram.com/p/{code}/" if code else None

            # Imagen de miniatura
            thumb = None
            thumb_url = getattr(media, "thumbnail_url", None)
            if thumb_url:
                thumb = json.dumps([str(thumb_url)])

            # Perfil del autor
            if username:
                upsert_account_profile(
                    db=self.db,
                    platform_id=self.platform.id,
                    username=username,
                    external_user_id=user_id,
                    followers_count=getattr(user, "follower_count", None),
                    following_count=getattr(user, "following_count", None),
                    post_count=getattr(user, "media_count", None),
                    verified=getattr(user, "is_verified", False),
                    has_profile_photo=bool(getattr(user, "profile_pic_url", None)),
                    display_name=getattr(user, "full_name", None),
                )

            mention = save_mention(
                db=self.db,
                platform_id=self.platform.id,
                entity_id=entity.id,
                external_id=f"ig_{media_pk}",
                content=caption or f"[Post de Instagram tipo {media_type}]",
                author_username=username,
                author_ext_id=user_id,
                url=url,
                published_at=taken_at,
                country_code=entity.country_code,
                reach=reach,
                matched_keywords=[keyword_obj],
                media_urls=thumb,
            )
            if mention:
                saved += 1

        return saved
