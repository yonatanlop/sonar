"""
Clase base y utilidades compartidas para todos los scrapers SONAR.
"""
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.entity import Entity, Keyword
from app.models.mention import Mention, SocialPlatform
from app.models.bot import AccountProfile

logger = logging.getLogger(__name__)


# ── Limpieza de texto ─────────────────────────────────────────

_URL_RE    = re.compile(r"https?://\S+")
_EMOJI_RE  = re.compile("["
    u"\U0001F600-\U0001F64F"
    u"\U0001F300-\U0001F5FF"
    u"\U0001F680-\U0001F9FF"
    u"\U00002700-\U000027BF"
    "]+", flags=re.UNICODE)
_SPACE_RE  = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Elimina URLs, emojis y espacios extra para análisis NLP."""
    if not text:
        return ""
    text = _URL_RE.sub(" ", text)
    text = _EMOJI_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text


def truncate(text: str, max_len: int = 5000) -> str:
    return text[:max_len] if text else ""


# ── Helpers de persistencia ───────────────────────────────────

def get_platform(db: Session, code: str) -> Optional[SocialPlatform]:
    return db.query(SocialPlatform).filter(SocialPlatform.code == code).first()


def upsert_account_profile(
    db: Session,
    platform_id: int,
    username: str,
    external_user_id: Optional[str] = None,
    **kwargs,
) -> AccountProfile:
    """Crea o actualiza el perfil de una cuenta. Retorna el objeto AccountProfile."""
    profile = None
    if external_user_id:
        profile = db.query(AccountProfile).filter(
            AccountProfile.platform_id == platform_id,
            AccountProfile.external_user_id == external_user_id,
        ).first()

    if not profile:
        profile = db.query(AccountProfile).filter(
            AccountProfile.platform_id == platform_id,
            AccountProfile.username == username,
        ).first()

    if profile:
        for k, v in kwargs.items():
            if v is not None:
                setattr(profile, k, v)
        profile.last_analyzed_at = datetime.now(timezone.utc)
    else:
        profile = AccountProfile(
            platform_id=platform_id,
            username=username,
            external_user_id=external_user_id,
            last_analyzed_at=datetime.now(timezone.utc),
            **kwargs,
        )
        db.add(profile)

    db.flush()
    return profile


def save_mention(
    db: Session,
    platform_id: int,
    entity_id,
    external_id: str,
    content: str,
    author_username: Optional[str] = None,
    author_ext_id: Optional[str] = None,
    url: Optional[str] = None,
    published_at: Optional[datetime] = None,
    language: Optional[str] = None,
    country_code: Optional[str] = None,
    reach: int = 0,
    matched_keywords: Optional[list] = None,
    media_urls: Optional[str] = None,   # JSON array de URLs de imágenes (módulo 7)
) -> Optional[Mention]:
    """
    Guarda una mención nueva. Retorna None si ya existe (duplicado).
    Después de guardar, la encola en Redis para procesamiento NLP.
    """
    # Verificar duplicado
    exists = db.query(Mention.id).filter(
        Mention.platform_id == platform_id,
        Mention.external_id == external_id,
    ).first()
    if exists:
        return None

    content_clean = clean_text(content)

    mention = Mention(
        entity_id=entity_id,
        platform_id=platform_id,
        external_id=external_id,
        content=truncate(content),
        content_clean=truncate(content_clean),
        author_username=author_username,
        author_ext_id=author_ext_id,
        url=url,
        published_at=published_at,
        language=language,
        country_code=country_code,
        reach=reach,
        processed=False,
        media_urls=media_urls,
    )
    db.add(mention)

    if matched_keywords:
        mention.keywords.extend(matched_keywords)

    db.flush()

    # Encolar para NLP
    try:
        import redis
        from app.core.config import settings
        r = redis.from_url(settings.REDIS_URL)
        r.lpush("nlp:pending", str(mention.id))
    except Exception as e:
        logger.warning(f"No se pudo encolar mención para NLP: {e}")

    return mention


def get_active_entities_with_keywords(db: Session) -> list[tuple[Entity, list[Keyword]]]:
    """Retorna todas las entidades activas con sus keywords activas."""
    entities = db.query(Entity).filter(Entity.active == True).all()
    result = []
    for entity in entities:
        keywords = [k for k in entity.keywords if k.active]
        if keywords:
            result.append((entity, keywords))
    return result


def build_search_terms(entity: Entity, keywords: list[Keyword]) -> list[tuple[str, Keyword]]:
    """
    Construye lista de (término_de_búsqueda, keyword_obj).
    Incluye keywords y aliases, priorizando las de mayor peso.
    """
    terms = []
    seen = set()

    # Keywords ordenadas por peso descendente
    for kw in sorted(keywords, key=lambda k: k.weight, reverse=True):
        term = kw.keyword.strip()
        if term.lower() not in seen:
            seen.add(term.lower())
            terms.append((term, kw))

    # Aliases de la entidad
    for alias in entity.aliases:
        term = alias.alias.strip()
        if term.lower() not in seen:
            seen.add(term.lower())
            # Buscar keyword más relevante para el alias
            best_kw = sorted(keywords, key=lambda k: k.weight, reverse=True)[0]
            terms.append((term, best_kw))

    return terms


# ── Clase base ────────────────────────────────────────────────

class BaseScraper:
    """Clase base para todos los scrapers SONAR."""

    platform_code: str = ""

    def __init__(self, db: Session):
        self.db = db
        self.platform = get_platform(db, self.platform_code)
        if not self.platform:
            raise ValueError(f"Plataforma '{self.platform_code}' no encontrada en BD")

    def scrape_all(self) -> dict:
        """
        Punto de entrada principal. Itera todas las entidades activas
        y ejecuta el scraping para cada una.
        Retorna resumen: {entity_name: mentions_saved}
        """
        entities_keywords = get_active_entities_with_keywords(self.db)
        summary = {}

        for entity, keywords in entities_keywords:
            try:
                saved = self.scrape_entity(entity, keywords)
                summary[entity.name] = saved
                self.db.commit()
                logger.info(f"[{self.platform_code}] {entity.name}: {saved} menciones nuevas")
            except Exception as e:
                self.db.rollback()
                logger.error(f"[{self.platform_code}] Error en {entity.name}: {e}")
                summary[entity.name] = 0

        return summary

    def scrape_entity(self, entity: Entity, keywords: list[Keyword]) -> int:
        """
        Implementar en cada subclase.
        Retorna número de menciones nuevas guardadas.
        """
        raise NotImplementedError
