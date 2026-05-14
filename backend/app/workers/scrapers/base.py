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
    """
    Crea o actualiza el perfil de una cuenta usando INSERT ... ON CONFLICT DO UPDATE
    para evitar UniqueViolation cuando dos workers concurrentes procesan el mismo perfil.
    """
    import uuid as _uuid
    now = datetime.now(timezone.utc)

    # Campos a insertar
    values = {
        "id":               _uuid.uuid4(),
        "platform_id":      platform_id,
        "username":         username,
        "external_user_id": external_user_id,
        "last_analyzed_at": now,
    }
    for k, v in kwargs.items():
        if v is not None:
            values[k] = v

    # Campos a actualizar en caso de conflicto (excluye id y platform_id)
    update_fields = {k: v for k, v in values.items() if k not in ("id", "platform_id")}

    stmt = pg_insert(AccountProfile).values(**values)

    if external_user_id:
        # Conflicto por (platform_id, external_user_id)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_platform_user",
            set_=update_fields,
        )
    else:
        # Conflicto por (platform_id, username) — sin external_user_id
        stmt = stmt.on_conflict_do_update(
            index_elements=["platform_id", "username"],
            set_=update_fields,
        )

    db.execute(stmt)
    db.flush()

    # Retornar el objeto actualizado
    profile = db.query(AccountProfile).filter(
        AccountProfile.platform_id == platform_id,
        AccountProfile.external_user_id == external_user_id,
    ).first() if external_user_id else db.query(AccountProfile).filter(
        AccountProfile.platform_id == platform_id,
        AccountProfile.username == username,
    ).first()

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
    media_urls: Optional[str] = None,        # JSON array de URLs de imágenes (módulo 7)
    conversation_id: Optional[str] = None,   # ID del hilo/conversación en Twitter
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
        language=language[:2] if language else None,
        country_code=country_code[:2] if country_code else None,
        reach=reach,
        processed=False,
        media_urls=media_urls,
        conversation_id=conversation_id,
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


def build_twitter_query(kw: "Keyword") -> str:
    """Construye el término de búsqueda para Twitter aplicando logic_op."""
    primary = kw.keyword.strip()
    secondary = (kw.keyword_secondary or "").strip()
    op = getattr(kw, "logic_op", "AND")

    if not secondary:
        return primary

    if op == "OR":
        return f'({primary} OR {secondary})'
    if op == "NOT":
        return f'{primary} -{secondary}'
    # AND (default)
    return f'{primary} {secondary}'


def keyword_matches_text(text: str, kw: "Keyword") -> bool:
    """Evalúa si un texto cumple con la expresión lógica de la keyword."""
    if not text:
        return False
    t = text.lower()
    primary = kw.keyword.strip().lower()
    secondary = (kw.keyword_secondary or "").strip().lower()
    op = getattr(kw, "logic_op", "AND")

    has_primary = primary in t
    if not has_primary:
        return False
    if not secondary:
        return True

    has_secondary = secondary in t
    if op == "OR":
        return True  # primary already found
    if op == "NOT":
        return not has_secondary
    # AND
    return has_secondary


def build_search_terms(entity: Entity, keywords: list[Keyword]) -> list[tuple[str, Keyword]]:
    """
    Construye lista de (término_de_búsqueda, keyword_obj).
    El término ya incluye el operador lógico para plataformas como Twitter.
    Para plataformas con búsqueda local usar keyword_matches_text() en el post-filtro.
    """
    terms = []
    seen = set()

    # Keywords ordenadas por peso descendente
    for kw in sorted(keywords, key=lambda k: k.weight, reverse=True):
        term = build_twitter_query(kw)
        key = term.lower()
        if key not in seen:
            seen.add(key)
            terms.append((term, kw))

    # Aliases de la entidad (sin operador secundario)
    for alias in entity.aliases:
        term = alias.alias.strip()
        if term.lower() not in seen:
            seen.add(term.lower())
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
