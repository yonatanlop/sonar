"""
RSSScraper — usa feedparser + newspaper3k.
Sin API keys, sin límites, completamente gratuito.

Monitorea fuentes RSS de noticias organizadas por país/idioma.
Filtra artículos que contengan keywords de las entidades monitoreadas.
"""
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
from sqlalchemy.orm import Session

from app.models.entity import Entity, Keyword
from app.workers.scrapers.base import (
    BaseScraper, build_search_terms, keyword_matches_text, save_mention, upsert_account_profile,
)

logger = logging.getLogger(__name__)

DELAY_BETWEEN_FEEDS = 1   # segundo entre feeds


# ── Fuentes RSS por país e idioma ─────────────────────────────
# Agregar/quitar feeds según necesidades del cliente.
# Formato: { 'country_code': [('nombre_medio', 'url_rss', 'idioma')] }

RSS_SOURCES = {
    "CO": [
        ("El Tiempo",       "https://www.eltiempo.com/rss/",                       "es"),
        ("El Colombiano",   "https://www.elcolombiano.com/rss/content_rss.xml",    "es"),
        ("Semana",          "https://www.semana.com/rss/",                         "es"),
        ("El Espectador",   "https://www.elespectador.com/arc/outboundfeeds/rss/", "es"),
        ("La República",    "https://www.larepublica.co/rss/",                     "es"),
    ],
    "MX": [
        ("El Universal",    "https://www.eluniversal.com.mx/rss.xml",              "es"),
        ("Reforma",         "https://www.reforma.com/rss/portada.xml",             "es"),
        ("Proceso",         "https://www.proceso.com.mx/rss/",                     "es"),
    ],
    "AR": [
        ("Infobae",         "https://www.infobae.com/feeds/rss/",                  "es"),
        ("La Nación",       "https://www.lanacion.com.ar/arc/outboundfeeds/rss/",  "es"),
        ("Clarín",          "https://www.clarin.com/rss/",                         "es"),
    ],
    "VE": [
        ("El Nacional",     "https://www.elnacional.com/feed/",                    "es"),
        ("Tal Cual",        "https://talcualdigital.com/feed/",                    "es"),
    ],
    "PE": [
        ("El Comercio",     "https://elcomercio.pe/rss/",                          "es"),
        ("La República",    "https://larepublica.pe/rss/",                         "es"),
    ],
    "CL": [
        ("La Tercera",      "https://www.latercera.com/feed/",                     "es"),
        ("El Mostrador",    "https://www.elmostrador.cl/feed/",                    "es"),
    ],
    "US": [
        ("BBC Mundo",       "https://feeds.bbci.co.uk/mundo/rss.xml",              "es"),
        ("CNN Español",     "https://cnnespanol.cnn.com/feed/",                    "es"),
        ("BBC News EN",     "https://feeds.bbci.co.uk/news/world/rss.xml",         "en"),
    ],
    "ES": [
        ("El País",         "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada", "es"),
        ("El Mundo",        "https://e00-elmundo.uecdn.es/elmundo/rss/portada.xml","es"),
    ],
}

# Fuentes globales que se monitoran siempre (sin importar el país de la entidad)
GLOBAL_SOURCES = [
    ("BBC Mundo",       "https://feeds.bbci.co.uk/mundo/rss.xml",  "es"),
    ("CNN Español",     "https://cnnespanol.cnn.com/feed/",         "es"),
    ("DW Español",      "https://rss.dw.com/rdf/rss-spa-all",       "es"),
]


class RSSScraper(BaseScraper):
    platform_code = "rss"

    def __init__(self, db: Session):
        super().__init__(db)
        self._feed_cache: dict = {}   # url → parsed feed (evita pedir el mismo feed dos veces)

    def scrape_entity(self, entity: Entity, keywords: list[Keyword]) -> int:
        saved_total = 0
        search_terms = build_search_terms(entity, keywords)
        keyword_terms = [t.lower() for t, _ in search_terms]

        # Construir dict term → keyword_obj para el matching
        term_to_kw = {t.lower(): kw for t, kw in search_terms}

        # Determinar fuentes a monitorear para esta entidad
        sources = list(GLOBAL_SOURCES)
        if entity.country_code and entity.country_code in RSS_SOURCES:
            sources += RSS_SOURCES[entity.country_code]

        for source_name, feed_url, lang in sources:
            try:
                saved = self._process_feed(
                    feed_url=feed_url,
                    source_name=source_name,
                    lang=lang,
                    entity=entity,
                    keyword_terms=keyword_terms,
                    term_to_kw=term_to_kw,
                )
                saved_total += saved
                time.sleep(DELAY_BETWEEN_FEEDS)
            except Exception as e:
                logger.warning(f"[RSS] Error procesando '{source_name}': {e}")

        return saved_total

    def _process_feed(
        self,
        feed_url: str,
        source_name: str,
        lang: str,
        entity: Entity,
        keyword_terms: list[str],
        term_to_kw: dict,
    ) -> int:
        saved = 0

        # Usar caché para no descargar el mismo feed varias veces en el mismo ciclo
        if feed_url not in self._feed_cache:
            feed = feedparser.parse(feed_url)
            if feed.bozo and not feed.entries:
                logger.debug(f"[RSS] Feed inaccesible: {feed_url}")
                self._feed_cache[feed_url] = None
                return 0
            self._feed_cache[feed_url] = feed
        else:
            feed = self._feed_cache[feed_url]

        if not feed:
            return 0

        for entry in feed.entries:
            title   = entry.get("title", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            content_text = f"{title}. {summary}".strip()

            # Verificar si el artículo cumple la expresión lógica de alguna keyword
            matched_kw_objs = [
                kw for kw in term_to_kw.values()
                if keyword_matches_text(content_text, kw)
            ]
            if not matched_kw_objs:
                continue

            best_kw = max(matched_kw_objs, key=lambda k: k.weight)

            # URL y external_id del artículo
            url = entry.get("link", "")
            # external_id: hash de la URL para tener un ID estable
            ext_id = hashlib.md5(url.encode()).hexdigest() if url else hashlib.md5(content_text[:200].encode()).hexdigest()

            # Fecha de publicación
            published_at = self._parse_date(entry)

            # Fuente como "cuenta autora"
            upsert_account_profile(
                db=self.db,
                platform_id=self.platform.id,
                username=source_name,
                external_user_id=f"source_{hashlib.md5(feed_url.encode()).hexdigest()[:8]}",
                display_name=source_name,
                verified=True,          # medios verificados
                has_profile_photo=False,
            )

            # Extraer imagen destacada del artículo para reconocimiento visual (módulo 7)
            media_urls = None
            try:
                img_url = None
                # feedparser puede exponer la imagen en media_content o enclosures
                media_content = entry.get("media_content", [])
                if media_content:
                    img_url = media_content[0].get("url")
                if not img_url:
                    enclosures = entry.get("enclosures", [])
                    for enc in enclosures:
                        if enc.get("type", "").startswith("image/"):
                            img_url = enc.get("href") or enc.get("url")
                            break
                if not img_url:
                    # og:image a veces aparece como tags
                    for tag in entry.get("tags", []):
                        term = tag.get("term", "")
                        if term.startswith("http") and any(
                            term.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png")
                        ):
                            img_url = term
                            break
                if img_url:
                    media_urls = json.dumps([img_url])
            except Exception:
                pass

            mention = save_mention(
                db=self.db,
                platform_id=self.platform.id,
                entity_id=entity.id,
                external_id=ext_id,
                content=content_text,
                author_username=source_name,
                author_ext_id=f"source_{hashlib.md5(feed_url.encode()).hexdigest()[:8]}",
                url=url,
                published_at=published_at,
                language=lang,
                country_code=entity.country_code,
                reach=0,
                matched_keywords=[best_kw],
                media_urls=media_urls,
            )
            if mention:
                saved += 1

        return saved

    @staticmethod
    def _parse_date(entry) -> Optional[datetime]:
        # feedparser a veces pone la fecha en published_parsed (time.struct_time)
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                import calendar
                ts = calendar.timegm(entry.published_parsed)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                pass

        # Intentar parsear el string directamente
        date_str = entry.get("published") or entry.get("updated") or ""
        if date_str:
            try:
                return parsedate_to_datetime(date_str)
            except Exception:
                pass

        return datetime.now(timezone.utc)
