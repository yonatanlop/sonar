"""
TwitterScraper — modo híbrido tri-nivel: twscrape → API v2 → Nitter.

Estrategia:
  1. Intenta twscrape (cookies de cuenta real). Si falla/timeout → tier 2.
  2. Intenta Twitter API v2 con Bearer Token (oficial, 500K tweets/mes gratis). Si falla → tier 3.
  3. Nitter como último recurso (instancias públicas, actualmente mayormente caídas).

Setup:
    Tier 1 — cuenta Twitter:
        docker compose exec backend python scripts/add_twitter_account.py
    Tier 2 — Bearer Token (recomendado):
        developer.twitter.com → Projects & Apps → Keys and Tokens → Bearer Token
        Agregar en .env: TWITTER_BEARER_TOKEN=AAAAAAAAAAAAAAAAAAAAAxxxxxx...

Rate limits:
    twscrape:    ~50 búsquedas / 15 min por cuenta
    API v2 free: 500K tweets/mes, búsqueda últimos 7 días
    Nitter:      sin límite estricto, dependiente de instancias activas
"""
import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entity import Entity, Keyword
from app.workers.scrapers.base import (
    BaseScraper, build_search_terms, save_mention, upsert_account_profile,
)

logger = logging.getLogger(__name__)

DELAY_BETWEEN_SEARCHES = 4   # segundos entre búsquedas
TWSCRAPE_TIMEOUT       = 30  # segundos máx esperando twscrape antes de ir a Nitter

# Instancias Nitter públicas — se prueban en orden hasta encontrar una activa
# Lista actualizada: prioriza instancias con búsqueda habilitada
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.nl",
    "https://nitter.mint.lgbt",
    "https://nitter.bird.froth.zone",
    "https://nitter.1d4.us",
    "https://nitter.poast.org",
    "https://nitter.unixfox.eu",
    "https://nitter.kavin.rocks",
]


def _since_date() -> str:
    since = datetime.now(timezone.utc) - timedelta(days=settings.TWITTER_LOOKBACK_DAYS)
    return since.strftime("%Y-%m-%d")


# ── Nitter helpers ─────────────────────────────────────────────────────────

def _parse_nitter_date(raw: str) -> datetime | None:
    """Parsea la fecha del atributo title de Nitter ('Jan 1, 2024 · 10:30 AM UTC')."""
    if not raw:
        return None
    # Nitter usa formato: "Mar 27, 2026 · 2:15 PM UTC"
    raw = raw.replace(" · ", " ").replace(" UTC", "").strip()
    for fmt in ("%b %d, %Y %I:%M %p", "%b %d, %Y %H:%M"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _nitter_tweet_id(url_path: str) -> str:
    """Genera un ID estable a partir del path del tweet en Nitter."""
    # path típico: /username/status/1234567890#m
    parts = url_path.rstrip("#m").split("/")
    for p in reversed(parts):
        if p.isdigit():
            return p
    # fallback: hash del path
    return "nitter_" + hashlib.md5(url_path.encode()).hexdigest()[:16]


def _parse_nitter_page(html: str, instance_base: str, limit: int) -> list[dict]:
    """Parsea una página de resultados de Nitter y retorna lista de tweets."""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for item in soup.select(".timeline-item"):
        if len(results) >= limit:
            break
        try:
            # Contenido
            content_el = item.select_one(".tweet-content")
            if not content_el:
                continue
            content = content_el.get_text(separator=" ", strip=True)

            # Autor
            username_el = item.select_one(".username")
            username = username_el.get_text(strip=True).lstrip("@") if username_el else None

            # Fecha
            date_el = item.select_one(".tweet-date a")
            published_at = None
            tweet_path = ""
            if date_el:
                published_at = _parse_nitter_date(date_el.get("title", ""))
                tweet_path = date_el.get("href", "")

            # ID del tweet
            tweet_id = _nitter_tweet_id(tweet_path) if tweet_path else None
            if not tweet_id:
                continue

            # URL canónica (x.com)
            if tweet_path:
                # /username/status/ID → https://x.com/username/status/ID
                url = "https://x.com" + tweet_path.split("#")[0]
            else:
                url = None

            # Engagement
            stats = item.select(".tweet-stat span:last-child")
            nums = []
            for s in stats:
                try:
                    nums.append(int(s.get_text(strip=True).replace(",", "") or 0))
                except ValueError:
                    nums.append(0)
            reach = sum(nums)

            results.append({
                "id":           tweet_id,
                "content":      content,
                "username":     username,
                "published_at": published_at,
                "url":          url,
                "reach":        reach,
            })
        except Exception as exc:
            logger.debug(f"[Nitter] Error parseando item: {exc}")
            continue

    return results


async def _twitter_api_v2_search(
    query: str,
    bearer_token: str,
    limit: int = 100,
) -> list[dict]:
    """
    Busca tweets usando Twitter API v2 Recent Search.
    Endpoint: GET https://api.twitter.com/2/tweets/search/recent
    Plan gratuito: 500K tweets/mes, últimos 7 días.
    """
    # La API v2 no acepta modificadores como (lang:es OR lang:en) junto con -is:retweet
    # en el tier gratuito — simplificamos la query a solo el término entre comillas
    # La query de twscrape ya incluye since:YYYY-MM-DD que no soporta API v2
    # → Extraemos solo la parte del término (entre las primeras comillas)
    import re as _re
    # Extraer término puro: '"término"' de '"término" (lang:...) ...'
    m = _re.match(r'^"([^"]+)"', query.strip())
    clean_term = m.group(1) if m else query.split()[0].strip('"')

    # Query para API v2: excluye retweets, requiere idioma es o en
    api_query = f'"{clean_term}" -is:retweet (lang:es OR lang:en)'

    params = {
        "query":        api_query,
        "max_results":  min(limit, 100),   # máximo permitido por request en plan Basic
        "tweet.fields": "created_at,author_id,public_metrics,lang",
        "user.fields":  "username,name,public_metrics,verified,created_at,description,profile_image_url",
        "expansions":   "author_id",
    }

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "User-Agent":    "SONAR-Monitor/2.0",
    }

    results = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://api.twitter.com/2/tweets/search/recent",
                params=params,
                headers=headers,
            )
            if resp.status_code == 429:
                logger.warning("[Twitter/APIv2] Rate limit alcanzado (429)")
                return []
            if resp.status_code != 200:
                logger.warning(f"[Twitter/APIv2] HTTP {resp.status_code}: {resp.text[:200]}")
                return []

            data = resp.json()
            tweets_raw = data.get("data", [])
            users_raw  = data.get("includes", {}).get("users", [])
            users_map  = {u["id"]: u for u in users_raw}

            for tw in tweets_raw:
                metrics = tw.get("public_metrics", {})
                reach = (
                    metrics.get("like_count",    0)
                    + metrics.get("retweet_count", 0)
                    + metrics.get("reply_count",   0)
                    + metrics.get("quote_count",   0)
                )
                author_id = tw.get("author_id")
                user = users_map.get(author_id, {})
                username = user.get("username")

                published_at = None
                raw_date = tw.get("created_at")
                if raw_date:
                    try:
                        published_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                    except ValueError:
                        pass

                tweet_id = tw["id"]
                url = f"https://x.com/{username}/status/{tweet_id}" if username else f"https://x.com/i/web/status/{tweet_id}"

                results.append({
                    "id":           tweet_id,
                    "content":      tw.get("text", ""),
                    "username":     username,
                    "author_id":    author_id,
                    "published_at": published_at,
                    "url":          url,
                    "reach":        reach,
                    "language":     tw.get("lang"),
                    "user":         user,
                })

    except Exception as exc:
        logger.warning(f"[Twitter/APIv2] Error en búsqueda: {exc}")
        return []

    logger.info(f"[Twitter/APIv2] '{clean_term}': {len(results)} tweets")
    return results


async def _nitter_search(query: str, limit: int = 100) -> list[dict]:
    """
    Busca tweets via Nitter. Rota por instancias hasta obtener resultados.
    Retorna lista de dicts con los campos del tweet.
    """
    encoded = quote_plus(query)

    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; SONAR-monitor/1.0)"},
        proxy=settings.TWITTER_PROXY_URL or None,
    ) as client:
        for instance in NITTER_INSTANCES:
            url = f"{instance}/search?q={encoded}&f=tweets"
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.debug(f"[Nitter] {instance} → HTTP {resp.status_code}, probando siguiente")
                    continue
                # Verificar que es una página Nitter válida con resultados o búsqueda activa
                body = resp.text
                search_disabled = (
                    "search is disabled" in body.lower()
                    or "instance does not support search" in body.lower()
                    or "search not available" in body.lower()
                )
                is_valid_nitter = (
                    "timeline-item" in body
                    or "no results" in body.lower()
                    or "nothing here" in body.lower()
                )
                if search_disabled or not is_valid_nitter:
                    logger.debug(f"[Nitter] {instance} → sin resultados válidos o búsqueda deshabilitada")
                    continue

                tweets = _parse_nitter_page(resp.text, instance, limit)
                logger.info(f"[Nitter] {instance} → {len(tweets)} tweets para '{query}'")
                return tweets

            except Exception as exc:
                logger.debug(f"[Nitter] {instance} → error: {exc}")
                continue

    logger.warning(f"[Nitter] Ninguna instancia disponible para '{query}'")
    return []


# ── Scraper principal ──────────────────────────────────────────────────────

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

    # ── Búsqueda híbrida ───────────────────────────────────────

    async def _search_and_save(
        self, term: str, entity: Entity, keyword_obj: Keyword
    ) -> int:
        since = _since_date()
        query = f'"{term}" (lang:es OR lang:en) -is:retweet since:{since}'

        # ── Intento 1: twscrape con timeout ────────────────────
        try:
            api = self._build_api()
            accounts = await api.pool.get_all()
            active = [a for a in accounts if getattr(a, "active", True)]

            if not active:
                logger.warning("[Twitter] Sin cuentas activas → Nitter")
                raise RuntimeError("no_active_accounts")

            # Timeout para evitar bloqueo infinito cuando twscrape espera
            # que las cuentas se desbloqueen (cada 15 min por Cloudflare)
            saved = await asyncio.wait_for(
                self._twscrape_search(api, query, entity, keyword_obj),
                timeout=TWSCRAPE_TIMEOUT,
            )
            logger.info(f"[Twitter/twscrape] '{term}': {saved} menciones nuevas")
            return saved

        except asyncio.TimeoutError:
            logger.warning(
                f"[Twitter/twscrape] Timeout ({TWSCRAPE_TIMEOUT}s) en '{term}' "
                "— cuentas bloqueadas por Cloudflare → API v2"
            )
        except Exception as exc:
            logger.warning(f"[Twitter/twscrape] Falló '{term}' ({exc}) → API v2")

        # ── Intento 2: Twitter API v2 (Bearer Token) ───────────
        bearer = settings.TWITTER_BEARER_TOKEN
        if bearer:
            try:
                saved = await self._apiv2_save(query, term, entity, keyword_obj, bearer)
                logger.info(f"[Twitter/APIv2] '{term}': {saved} menciones nuevas")
                return saved
            except Exception as exc:
                logger.warning(f"[Twitter/APIv2] Falló '{term}' ({exc}) → Nitter")
        else:
            logger.debug("[Twitter/APIv2] TWITTER_BEARER_TOKEN no configurado, saltando tier 2")

        # ── Intento 3: Nitter fallback ─────────────────────────
        saved = await self._nitter_save(query, term, entity, keyword_obj)
        logger.info(f"[Twitter/Nitter] '{term}': {saved} menciones nuevas")
        return saved

    # ── twscrape search ────────────────────────────────────────

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

                except Exception as exc:
                    logger.warning(f"[Twitter/twscrape] Error procesando tweet {getattr(tweet, 'id', '?')}: {exc}")
                    continue

        except Exception as exc:
            # Re-lanzar para que _search_and_save active el fallback Nitter
            raise exc

        return saved

    # ── Twitter API v2 save ────────────────────────────────────

    async def _apiv2_save(
        self, query: str, term: str,
        entity: Entity, keyword_obj: Keyword,
        bearer_token: str,
    ) -> int:
        tweets = await _twitter_api_v2_search(
            query, bearer_token, limit=settings.TWITTER_MAX_RESULTS
        )
        saved = 0

        for tw in tweets:
            try:
                user = tw.get("user", {})
                if user:
                    u_metrics = user.get("public_metrics", {})
                    upsert_account_profile(
                        db=self.db,
                        platform_id=self.platform.id,
                        username=user["username"],
                        external_user_id=user.get("id"),
                        display_name=user.get("name"),
                        followers_count=u_metrics.get("followers_count"),
                        following_count=u_metrics.get("following_count"),
                        post_count=u_metrics.get("tweet_count"),
                        has_profile_photo=bool(user.get("profile_image_url")),
                        verified=user.get("verified", False),
                        account_created=(
                            datetime.fromisoformat(
                                user["created_at"].replace("Z", "+00:00")
                            ).date()
                            if user.get("created_at") else None
                        ),
                        bio=user.get("description"),
                    )

                mention = save_mention(
                    db=self.db,
                    platform_id=self.platform.id,
                    entity_id=entity.id,
                    external_id=tw["id"],
                    content=tw["content"],
                    author_username=tw.get("username"),
                    author_ext_id=tw.get("author_id"),
                    url=tw.get("url"),
                    published_at=tw.get("published_at"),
                    language=tw.get("language"),
                    reach=tw.get("reach", 0),
                    matched_keywords=[keyword_obj],
                )
                if mention:
                    saved += 1
            except Exception as exc:
                logger.warning(f"[Twitter/APIv2] Error guardando tweet {tw.get('id')}: {exc}")
                continue

        return saved

    # ── Nitter save ────────────────────────────────────────────

    async def _nitter_save(
        self, query: str, term: str,
        entity: Entity, keyword_obj: Keyword,
    ) -> int:
        tweets = await _nitter_search(query, limit=settings.TWITTER_MAX_RESULTS)
        saved = 0

        for tw in tweets:
            try:
                mention = save_mention(
                    db=self.db,
                    platform_id=self.platform.id,
                    entity_id=entity.id,
                    external_id=tw["id"],
                    content=tw["content"],
                    author_username=tw.get("username"),
                    url=tw.get("url"),
                    published_at=tw.get("published_at"),
                    reach=tw.get("reach", 0),
                    matched_keywords=[keyword_obj],
                )
                if mention:
                    saved += 1
            except Exception as exc:
                logger.warning(f"[Twitter/Nitter] Error guardando tweet {tw.get('id')}: {exc}")
                continue

        return saved
