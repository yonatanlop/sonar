"""
TwitterScraper — usa twscrape para acceder a la API web de Twitter/X.
No requiere API key oficial de pago, pero necesita al menos 1 cuenta real.

Setup inicial (UNA SOLA VEZ, desde la carpeta sonar/):
    docker compose exec backend python scripts/add_twitter_account.py

Recomendado: agregar 2-3 cuentas para distribuir los rate limits.
Las cuentas se almacenan cifradas en: /app/storage/twscrape.db

Rate limits aproximados:
    1 cuenta  → ~50 búsquedas / 15 minutos
    3 cuentas → ~150 búsquedas / 15 minutos (twscrape rota automáticamente)
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entity import Entity, Keyword
from app.workers.scrapers.base import (
    BaseScraper, build_search_terms, save_mention, upsert_account_profile,
)

logger = logging.getLogger(__name__)

DELAY_BETWEEN_SEARCHES = 4    # segundos entre búsquedas (respetar rate limit)


def _since_date() -> str:
    """Devuelve la fecha de inicio para el filtro since: según TWITTER_LOOKBACK_DAYS."""
    since = datetime.now(timezone.utc) - timedelta(days=settings.TWITTER_LOOKBACK_DAYS)
    return since.strftime("%Y-%m-%d")


class TwitterScraper(BaseScraper):
    platform_code = "twitter"

    def __init__(self, db: Session):
        super().__init__(db)

    # ── API helper ─────────────────────────────────────────────

    def _build_api(self):
        """Crea instancia de twscrape.API apuntando a la DB de cuentas."""
        try:
            from twscrape import API
        except ImportError:
            raise RuntimeError(
                "twscrape no está instalado. "
                "Descomenta 'twscrape' en requirements.txt y reconstruye: "
                "docker compose build backend"
            )
        return API(settings.TWITTER_ACCOUNTS_DB)

    # ── Punto de entrada ───────────────────────────────────────

    def scrape_entity(self, entity: Entity, keywords: list[Keyword]) -> int:
        saved_total = 0
        search_terms = build_search_terms(entity, keywords)

        for term, keyword_obj in search_terms:
            try:
                saved = asyncio.run(self._search_and_save(term, entity, keyword_obj))
                saved_total += saved
                time.sleep(DELAY_BETWEEN_SEARCHES)
            except RuntimeError as e:
                logger.error(f"[Twitter] RuntimeError buscando '{term}': {e}")
            except Exception as e:
                logger.error(f"[Twitter] Error buscando '{term}': {e}")

        return saved_total

    # ── Lógica asíncrona ───────────────────────────────────────

    async def _search_and_save(
        self, term: str, entity: Entity, keyword_obj: Keyword
    ) -> int:
        api = self._build_api()

        # Verificar que hay cuentas activas en el pool
        try:
            accounts = await api.pool.get_all()
            active = [a for a in accounts if getattr(a, "active", True)]
            if not active:
                logger.warning(
                    "[Twitter] No hay cuentas activas en el pool. "
                    "Ejecuta: docker compose exec backend python scripts/add_twitter_account.py"
                )
                return 0
        except Exception as e:
            logger.error(f"[Twitter] Error al verificar cuentas del pool: {e}")
            return 0

        # Query: frase exacta, español o inglés, sin retweets, con ventana temporal
        since = _since_date()
        query = f'"{term}" (lang:es OR lang:en) -is:retweet since:{since}'
        saved = 0

        logger.debug(
            f"[Twitter] Buscando: {query}  (limit={settings.TWITTER_MAX_RESULTS})"
        )

        try:
            async for tweet in api.search(query, limit=settings.TWITTER_MAX_RESULTS):
                try:
                    user = tweet.user

                    # Guardar perfil del autor para análisis de bots
                    if user:
                        upsert_account_profile(
                            db=self.db,
                            platform_id=self.platform.id,
                            username=user.username,
                            external_user_id=str(user.id),
                            display_name=getattr(user, "displayname", None),
                            followers_count=getattr(user, "followersCount", None),
                            following_count=getattr(user, "friendsCount", None),
                            post_count=getattr(user, "statusesCount", None),
                            has_profile_photo=bool(getattr(user, "profileImageUrl", None)),
                            verified=(
                                bool(getattr(user, "verified", False))
                                or bool(getattr(user, "blue", False))
                            ),
                            account_created=(
                                user.created.date()
                                if getattr(user, "created", None) else None
                            ),
                            bio=getattr(user, "rawDescription", None),
                        )

                    # Guardar la mención
                    content = getattr(tweet, "rawContent", None) or tweet.content
                    url = getattr(
                        tweet, "url",
                        f"https://x.com/i/web/status/{tweet.id}"
                    )
                    reach = (
                        (getattr(tweet, "likeCount",    0) or 0)
                        + (getattr(tweet, "retweetCount", 0) or 0)
                        + (getattr(tweet, "replyCount",   0) or 0)
                        + (getattr(tweet, "quoteCount",   0) or 0)
                    )

                    # Extraer URLs de imágenes adjuntas al tweet (módulo 7)
                    media_urls = None
                    try:
                        media = getattr(tweet, "media", None) or []
                        img_urls = [
                            m.url for m in media
                            if hasattr(m, "url") and m.url
                            and any(m.url.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp"))
                        ]
                        if not img_urls:
                            # Algunos objetos usan previewUrl
                            img_urls = [
                                m.previewUrl for m in media
                                if hasattr(m, "previewUrl") and m.previewUrl
                            ]
                        if img_urls:
                            media_urls = json.dumps(img_urls[:4])  # máx 4 imágenes
                    except Exception:
                        pass

                    mention = save_mention(
                        db=self.db,
                        platform_id=self.platform.id,
                        entity_id=entity.id,
                        external_id=str(tweet.id),
                        content=content,
                        author_username=user.username if user else None,
                        author_ext_id=str(user.id) if user else None,
                        url=url,
                        published_at=tweet.date,
                        language=getattr(tweet, "lang", None),
                        reach=reach,
                        matched_keywords=[keyword_obj],
                        media_urls=media_urls,
                    )
                    if mention:
                        saved += 1

                except Exception as e:
                    logger.warning(
                        f"[Twitter] Error procesando tweet "
                        f"{getattr(tweet, 'id', '?')}: {e}"
                    )
                    continue

        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                logger.warning(
                    f"[Twitter] Rate limit alcanzado buscando '{term}'. "
                    "Esperando siguiente ciclo..."
                )
            elif "unauthorized" in err or "403" in err:
                logger.error(
                    f"[Twitter] Autenticación fallida para '{term}'. "
                    "Verifica las cuentas del pool."
                )
            else:
                logger.error(f"[Twitter] Error en búsqueda '{term}': {e}")

        return saved
