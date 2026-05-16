"""
TwitterScraper — Tier único: twscrape con autenticación robusta.

Estrategia (simplificada):
  Solo twscrape (cookies de cuenta real + TOTP automático).
  Tier 2 (API v2) y Tier 3 (Nitter) eliminados — no disponibles gratis.

Setup:
    Sin 2FA:
        docker compose exec worker python scripts/add_twitter_account.py \\
          --username TU_USUARIO --email TU@EMAIL.COM --password TU_CONTRASEÑA

    Con 2FA (recomendado para mayor estabilidad):
        docker compose exec worker python scripts/add_twitter_account.py \\
          --username TU_USUARIO --email TU@EMAIL.COM --password TU_CONTRASEÑA \\
          --totp-secret TU_SECRETO_BASE32

    El secreto base32 se encuentra en la URL del QR de 2FA:
        otpauth://totp/...?secret=AQUI_ESTA_EL_SECRETO

Rate limits:
    twscrape: ~50 búsquedas / 15 min por cuenta
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entity import Entity, Keyword
from app.workers.scrapers.base import (
    BaseScraper, build_search_terms, save_mention, upsert_account_profile,
)

logger = logging.getLogger(__name__)

DELAY_BETWEEN_SEARCHES = 4   # segundos entre búsquedas
TWSCRAPE_TIMEOUT       = 30  # segundos máx esperando twscrape por query


# ── Patch queue_client.py — usa xclienttransaction para x-client-transaction-id
def _patch_queue_client():
    """
    twscrape 0.17.0 usa xclid.py para generar x-client-transaction-id, pero
    xclid.py falla porque Twitter cambió cómo carga sus JS chunks.

    La librería xclienttransaction (PyPI: xclienttransaction) resuelve esto con
    un patrón diferente para encontrar el archivo ondemand.s.*.js.

    Parcheamos queue_client.XClIdGenStore.get() para que use xclienttransaction
    en lugar de xclid.py. Esto hace que cada búsqueda genere un header válido
    y Twitter responda 200 en lugar de 404.
    """
    try:
        import httpx as _httpx
        from x_client_transaction import ClientTransaction as _CT
        from x_client_transaction.utils import (
            handle_x_migration_async as _migrate,
            get_ondemand_file_url as _ondemand_url,
        )
        from twscrape import queue_client as _qc

        # Cache: (home_page_soup, ondemand_text) — se refresca cada 30 min
        _cache: dict = {}

        async def _get_ct() -> _CT:
            import time
            now = time.time()
            if "ct" not in _cache or now - _cache.get("ts", 0) > 1800:
                async with _httpx.AsyncClient(
                    follow_redirects=True,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/134.0.0.0 Safari/537.36"
                        ),
                        "X-Twitter-Active-User": "yes",
                        "X-Twitter-Client-Language": "en",
                    },
                ) as client:
                    home = await _migrate(client)
                    od_url = _ondemand_url(home)
                    od_rep = await client.get(od_url)
                _cache["ct"] = _CT(home, od_rep)
                _cache["ts"] = now
                logger.info("[Twitter] xclienttransaction cache actualizado")
            return _cache["ct"]

        # Monkey-patch: reemplaza XClIdGenStore.get con nuestra implementación
        class _PatchedXClIdGenStore:
            @staticmethod
            async def get(username: str, fresh: bool = False):
                """Retorna un objeto compatible con .calc() usando xclienttransaction."""
                ct = await _get_ct()

                class _Wrapper:
                    def __init__(self, ct_obj):
                        self._ct = ct_obj

                    def calc(self, method: str, path: str) -> str:
                        try:
                            return self._ct.generate_transaction_id(
                                method=method, path=path
                            )
                        except Exception as e:
                            logger.warning(f"[Twitter] xclienttransaction calc error: {e}")
                            return ""

                return _Wrapper(ct)

        _qc.XClIdGenStore = _PatchedXClIdGenStore

        # ── También parchear to_old_obj en utils.py (campos movidos de legacy a core/avatar)
        from twscrape import utils as _twutils

        _orig_to_old_obj = _twutils.to_old_obj

        def _patched_to_old_obj(obj: dict):
            # Twitter 2026: screen_name/name/created_at → core{}
            #               profile_image_url_https    → avatar.image_url
            core = obj.get("core", {})
            compat: dict = {}
            avatar_url = (obj.get("avatar") or {}).get("image_url")
            if avatar_url:
                compat["profile_image_url_https"] = avatar_url
            if "location" not in obj.get("legacy", {}):
                compat["location"] = core.get("location", "") or ""
            return {
                **obj,
                **core,
                **compat,
                **obj["legacy"],
                "id_str": str(obj["rest_id"]),
                "id": int(obj["rest_id"]),
                "legacy": None,
            }

        _twutils.to_old_obj = _patched_to_old_obj
        # Actualizar referencia en utils (to_old_rep llama to_old_obj en el mismo módulo)
        import twscrape.utils as _twutils2
        _twutils2.to_old_obj = _patched_to_old_obj

        # ── Actualizar queryIds de twscrape a los actuales (capturados de main.js)
        import twscrape.api as _tw_api
        _tw_api.OP_SearchTimeline          = "pCd62NDD9dlCDgEGgEVHMg/SearchTimeline"
        _tw_api.OP_UserByScreenName        = "IGgvgiOx4QZndDHuD3x9TQ/UserByScreenName"
        _tw_api.OP_TweetDetail             = "rU08O-YiXdr0IZfE7qaUMg/TweetDetail"
        _tw_api.OP_Followers               = "-WcGoRt8IQuPm-l1ymgy6g/Followers"
        _tw_api.OP_Following               = "vWCjN9gcTJiXzzMPR5Oxzw/Following"
        _tw_api.OP_UserTweets              = "x3B_xLqC0yZawOB7WQhaVQ/UserTweets"
        _tw_api.OP_UserTweetsAndReplies    = "Yt1JzwcBsBWYEEi3jMTe2Q/UserTweetsAndReplies"
        _tw_api.OP_ListLatestTweetsTimeline = "qcQY-EkEWjJ-wwJhsKdxYQ/ListLatestTweetsTimeline"
        _tw_api.OP_UserMedia               = "y4E0HTZKPhAOXewRMqMqgw/UserMedia"
        _tw_api.OP_GenericTimelineById     = "2My6Exw3i3JLnuoxc4my8A/GenericTimelineById"

        logger.info("[Twitter] queue_client + to_old_obj + queryIds patches aplicados OK")
    except ImportError:
        logger.warning("[Twitter] xclienttransaction no instalado — x-client-transaction-id no se generará")
    except Exception as e:
        logger.warning(f"[Twitter] No se pudo patchear queue_client: {e}")


_patch_queue_client()


def _since_date() -> str:
    since = datetime.now(timezone.utc) - timedelta(days=settings.TWITTER_LOOKBACK_DAYS)
    return since.strftime("%Y-%m-%d")


# ── Re-login helper ──────────────────────────────────────────────────────────

async def _relogin_all_accounts(api) -> dict:
    """Re-loguea todas las cuentas activas para renovar sesión."""
    pool = api.pool
    accounts = await pool.get_all()
    ok, fail = 0, 0
    for acc in accounts:
        try:
            await pool.login(acc.username)
            ok += 1
            logger.info(f"[Twitter] Re-login OK: @{acc.username}")
        except Exception as e:
            fail += 1
            logger.warning(f"[Twitter] Re-login FAIL @{acc.username}: {e}")
    return {"ok": ok, "fail": fail}


# ── Scraper principal ────────────────────────────────────────────────────────

async def scrape_feeds(db) -> dict:
    """
    Twitter Explorer — scraping de feeds de @usuarios y #hashtags.
    Lee todos los TwitterFeed activos y ejecuta búsquedas específicas.
    """
    from app.models.twitter_feed import TwitterFeed
    from app.workers.scrapers.base import save_mention, upsert_account_profile

    feeds = db.query(TwitterFeed).filter(TwitterFeed.active == True).all()
    if not feeds:
        return {"feeds": 0, "saved": 0}

    platform = db.query(
        __import__("app.models.mention", fromlist=["SocialPlatform"]).SocialPlatform
    ).filter_by(code="twitter").first()
    if not platform:
        return {"feeds": 0, "saved": 0, "error": "plataforma twitter no encontrada"}

    since = _since_date()
    api = TwitterScraper.__new__(TwitterScraper)
    api.db = db

    # Verificar disponibilidad de cuentas ANTES del loop para evitar timeouts
    tw_api = api._build_api()
    all_accounts = await tw_api.pool.get_all()
    active_accounts = [a for a in all_accounts if getattr(a, "active", True)]
    if not active_accounts:
        logger.warning("[TwitterExplorer] Sin cuentas activas — saltando")
        return {"feeds": len(feeds), "saved": 0, "skipped": "no_accounts"}

    # Detectar rate limit activo en SearchTimeline
    now = datetime.now(timezone.utc)
    rate_limited = True
    for acc in active_accounts:
        locks = getattr(acc, "locks", {}) or {}
        lock_until = locks.get("SearchTimeline")
        if lock_until is None or lock_until <= now:
            rate_limited = False
            break
    if rate_limited:
        earliest = min(
            (getattr(acc, "locks", {}).get("SearchTimeline") for acc in active_accounts),
            default=None,
        )
        logger.warning(f"[TwitterExplorer] Rate limit activo hasta {earliest} — saltando")
        return {"feeds": len(feeds), "saved": 0, "skipped": "rate_limit", "available_at": str(earliest)}

    total_saved = 0

    for feed in feeds:
        if not feed.entity_id:
            continue

        from app.models.entity import Entity as _Entity
        feed_entity = db.query(_Entity).filter(_Entity.id == feed.entity_id).first()
        feed_country = feed_entity.country_code if feed_entity else None

        term = feed.term.strip()
        if feed.feed_type == "user":
            query = f"from:{term} since:{since}"
        elif feed.feed_type == "hashtag":
            query = f"#{term} since:{since}"
        else:
            query = f'"{term}" (lang:es OR lang:en) -is:retweet since:{since}'

        try:
            saved = await asyncio.wait_for(
                _scrape_feed_query(tw_api, query, platform.id, feed.entity_id, db,
                                   country_code=feed_country),
                timeout=TWSCRAPE_TIMEOUT,
            )
            total_saved += saved
            logger.info(f"[TwitterExplorer] {feed.display_name}: {saved} nuevos tweets")
        except asyncio.TimeoutError:
            logger.warning(f"[TwitterExplorer] Timeout en {feed.display_name}")
        except Exception as exc:
            logger.warning(f"[TwitterExplorer] Error en {feed.display_name}: {exc}")

        await asyncio.sleep(DELAY_BETWEEN_SEARCHES)

    return {"feeds": len(feeds), "saved": total_saved}


async def _scrape_feed_query(api, query: str, platform_id: int, entity_id, db,
                            country_code: str | None = None) -> int:
    """Ejecuta una query de feed y guarda los tweets como menciones."""
    from app.workers.scrapers.base import save_mention, upsert_account_profile
    import json as _json

    saved = 0
    try:
        async for tweet in api.search(query, limit=settings.TWITTER_MAX_RESULTS):
            try:
                user = tweet.user
                if user:
                    upsert_account_profile(
                        db=db,
                        platform_id=platform_id,
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
                        location_text=(getattr(user, "location", None) or "")[:200] or None,
                    )

                content = getattr(tweet, "rawContent", None) or tweet.content
                url = getattr(tweet, "url", f"https://x.com/i/web/status/{tweet.id}")
                reach = (
                    (getattr(tweet, "likeCount",    0) or 0)
                    + (getattr(tweet, "retweetCount", 0) or 0)
                    + (getattr(tweet, "replyCount",   0) or 0)
                    + (getattr(tweet, "quoteCount",   0) or 0)
                )

                media_urls = None
                try:
                    media = getattr(tweet, "media", None) or []
                    img_urls = [
                        m.url for m in media
                        if hasattr(m, "url") and m.url
                        and any(m.url.lower().endswith(ext)
                                for ext in (".jpg", ".jpeg", ".png", ".webp"))
                    ]
                    if not img_urls:
                        img_urls = [
                            m.previewUrl for m in media
                            if hasattr(m, "previewUrl") and m.previewUrl
                        ]
                    if img_urls:
                        media_urls = _json.dumps(img_urls[:4])
                except Exception:
                    pass

                conv_id = str(getattr(tweet, "conversationId", None) or "") or None

                mention = save_mention(
                    db=db,
                    platform_id=platform_id,
                    entity_id=entity_id,
                    external_id=str(tweet.id),
                    content=content,
                    author_username=user.username if user else None,
                    author_ext_id=str(user.id) if user else None,
                    url=url,
                    published_at=tweet.date,
                    language=getattr(tweet, "lang", None),
                    country_code=country_code,
                    reach=reach,
                    media_urls=media_urls,
                    conversation_id=conv_id,
                )
                if mention:
                    saved += 1

            except Exception as exc:
                logger.warning(f"[TwitterExplorer] Error procesando tweet {getattr(tweet, 'id', '?')}: {exc}")
                continue
    except Exception as exc:
        raise exc

    return saved


class TwitterScraper(BaseScraper):
    platform_code = "twitter"

    def __init__(self, db: Session):
        super().__init__(db)

    def _build_api(self):
        try:
            from twscrape import API
        except ImportError:
            raise RuntimeError("twscrape no está instalado.")
        proxy = settings.TWITTER_PROXY_URL or None
        return API(settings.TWITTER_ACCOUNTS_DB, proxy=proxy)

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

    async def _search_and_save(
        self, term: str, entity: Entity, keyword_obj: Keyword
    ) -> int:
        since = _since_date()
        query = f'"{term}" (lang:es OR lang:en) -is:retweet since:{since}'

        try:
            api = self._build_api()
            accounts = await api.pool.get_all()
            active = [a for a in accounts if getattr(a, "active", True)]

            if not active:
                logger.warning("[Twitter] Sin cuentas activas en el pool — agrega una con add_twitter_account.py")
                return 0

            saved = await asyncio.wait_for(
                self._twscrape_search(api, query, entity, keyword_obj),
                timeout=TWSCRAPE_TIMEOUT,
            )
            logger.info(f"[twitter] Tier 1 OK — '{term}': {saved} menciones nuevas")
            return saved

        except asyncio.TimeoutError:
            logger.warning(
                f"[Twitter] Timeout ({TWSCRAPE_TIMEOUT}s) en '{term}' "
                "— cuenta en cooldown por rate-limit"
            )
            return 0
        except Exception as exc:
            logger.warning(f"[Twitter] Error en '{term}': {exc}")
            return 0

    async def _twscrape_search(
        self, api, query: str,
        entity: Entity, keyword_obj: Keyword,
    ) -> int:
        saved = 0
        try:
            async for tweet in api.search(query, limit=settings.TWITTER_MAX_RESULTS):
                try:
                    user = tweet.user
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
                            location_text=(getattr(user, "location", None) or "")[:200] or None,
                        )

                    content = getattr(tweet, "rawContent", None) or tweet.content
                    url = getattr(tweet, "url", f"https://x.com/i/web/status/{tweet.id}")
                    reach = (
                        (getattr(tweet, "likeCount",    0) or 0)
                        + (getattr(tweet, "retweetCount", 0) or 0)
                        + (getattr(tweet, "replyCount",   0) or 0)
                        + (getattr(tweet, "quoteCount",   0) or 0)
                    )

                    media_urls = None
                    try:
                        media = getattr(tweet, "media", None) or []
                        img_urls = [
                            m.url for m in media
                            if hasattr(m, "url") and m.url
                            and any(m.url.lower().endswith(ext)
                                    for ext in (".jpg", ".jpeg", ".png", ".webp"))
                        ]
                        if not img_urls:
                            img_urls = [
                                m.previewUrl for m in media
                                if hasattr(m, "previewUrl") and m.previewUrl
                            ]
                        if img_urls:
                            media_urls = json.dumps(img_urls[:4])
                    except Exception:
                        pass

                    conv_id = str(getattr(tweet, "conversationId", None) or "") or None

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
                        country_code=entity.country_code,
                        reach=reach,
                        matched_keywords=[keyword_obj],
                        media_urls=media_urls,
                        conversation_id=conv_id,
                    )
                    if mention:
                        saved += 1

                except Exception as exc:
                    logger.warning(f"[Twitter] Error procesando tweet {getattr(tweet, 'id', '?')}: {exc}")
                    continue

        except Exception as exc:
            raise exc

        return saved
