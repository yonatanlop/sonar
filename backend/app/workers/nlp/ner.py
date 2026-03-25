"""
Extracción de Entidades Nombradas (NER) — Módulo 1.2 v2

Usa spaCy con el modelo `es_core_news_sm` (12 MB, gratuito, sin API).
Extrae personas (PER), organizaciones (ORG) y lugares (LOC) que aparecen
junto a la entidad monitoreada, y los guarda en `mention_entities`.

La tarea Celery `extract_ner` corre cada hora sobre menciones de los
últimos 7 días que aún no han sido procesadas por NER.
"""
import logging
import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Tipos a extraer (mapeados desde etiquetas spaCy)
ALLOWED_TYPES = {"PER", "ORG", "LOC"}

# Mínimo de caracteres para considerar una entidad válida
MIN_ENTITY_LEN = 3

# Límite de menciones por ejecución
BATCH_LIMIT = 400


# ── Carga del modelo spaCy (singleton) ───────────────────────────

_nlp = None


def _load_nlp():
    """Carga el modelo spaCy `es_core_news_sm` con cache."""
    global _nlp
    if _nlp is not None:
        return _nlp

    try:
        import spacy
        _nlp = spacy.load("es_core_news_sm")
        logger.info("[NER] Modelo es_core_news_sm cargado correctamente")
    except OSError:
        # Modelo no descargado — intentar carga mínima
        try:
            import spacy
            _nlp = spacy.blank("es")
            logger.warning("[NER] es_core_news_sm no disponible; usando modelo en blanco (sin NER)")
        except Exception as exc:
            logger.error(f"[NER] No se pudo cargar spaCy: {exc}")
            _nlp = None

    return _nlp


# ── Extracción de entidades ───────────────────────────────────────

def _clean_entity_text(text: str) -> str:
    """Normaliza el texto de una entidad: strip, colapsar espacios."""
    return re.sub(r"\s+", " ", text.strip())


def extract_entities(text: str, entity_name: str = "") -> list[dict]:
    """
    Extrae entidades nombradas de un texto.
    Retorna lista de { entity_type: 'PER'|'ORG'|'LOC', entity_text: str }.
    Filtra la entidad monitoreada para evitar auto-referencias.
    """
    nlp = _load_nlp()
    if nlp is None or not text:
        return []

    # Truncar para no exceder límite de tokens (~512 tokens ≈ 2000 chars)
    doc = nlp(text[:2000])

    seen  = set()
    result = []
    entity_lower = entity_name.lower()

    for ent in doc.ents:
        etype = ent.label_
        etext = _clean_entity_text(ent.text)

        # Filtros
        if etype not in ALLOWED_TYPES:
            continue
        if len(etext) < MIN_ENTITY_LEN:
            continue
        if etext.lower() == entity_lower:
            continue   # no incluir la propia entidad monitoreada
        if etext.lower() in entity_lower or entity_lower in etext.lower():
            continue   # variantes del nombre de la entidad

        key = (etype, etext.lower())
        if key in seen:
            continue
        seen.add(key)

        result.append({"entity_type": etype, "entity_text": etext})

    return result


# ── Procesamiento por mención ─────────────────────────────────────

def _mention_already_processed(db, mention_id) -> bool:
    """Retorna True si la mención ya tiene al menos un registro en mention_entities."""
    from app.models.mention_entity import MentionEntity
    return db.query(MentionEntity.id).filter(
        MentionEntity.mention_id == mention_id
    ).first() is not None


def process_mention_ner(db, mention) -> int:
    """
    Extrae entidades de una mención y las guarda en `mention_entities`.
    Retorna el número de entidades guardadas.
    """
    from app.models.mention_entity import MentionEntity
    from app.models.entity import Entity

    # Obtener nombre de la entidad monitoreada para filtrado
    entity = db.query(Entity).filter(Entity.id == mention.entity_id).first()
    entity_name = entity.name if entity else ""

    text = mention.content_clean or mention.content or ""
    entities = extract_entities(text, entity_name)

    for ent in entities:
        db.add(MentionEntity(
            mention_id  = mention.id,
            entity_type = ent["entity_type"],
            entity_text = ent["entity_text"],
        ))

    # Marcar con un registro de "procesado" aunque no haya entidades,
    # para no re-procesar la mención en la siguiente ejecución.
    # Usamos un registro sentinel con entity_type="__done__" si lista vacía.
    if not entities:
        db.add(MentionEntity(
            mention_id  = mention.id,
            entity_type = "__done__",
            entity_text = "",
        ))

    return len(entities)


# ── Ejecución batch ───────────────────────────────────────────────

def run_ner_extraction(db, days: int = 7) -> dict:
    """
    Procesa las menciones recientes que aún no tienen NER.
    Llamado por la tarea Celery `extract_ner` cada hora.
    """
    from sqlalchemy import func, exists
    from app.models.mention import Mention
    from app.models.mention_entity import MentionEntity

    nlp = _load_nlp()
    if nlp is None:
        return {"status": "skipped", "reason": "spacy_not_available"}

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Menciones procesadas por NLP pero sin NER aún
    already_ner = db.query(MentionEntity.mention_id).distinct().subquery()
    mentions = (
        db.query(Mention)
        .filter(
            Mention.processed    == True,
            Mention.collected_at >= since,
            ~exists().where(already_ner.c.mention_id == Mention.id),
        )
        .order_by(Mention.collected_at.desc())
        .limit(BATCH_LIMIT)
        .all()
    )

    total_mentions  = len(mentions)
    total_entities  = 0
    errors          = 0

    for mention in mentions:
        try:
            n = process_mention_ner(db, mention)
            total_entities += n
        except Exception as exc:
            logger.error(f"[NER] Error en mención {mention.id}: {exc}", exc_info=True)
            errors += 1

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"[NER] Error en commit: {exc}", exc_info=True)
        errors += 1

    result = {
        "mentions_processed": total_mentions,
        "entities_extracted": total_entities,
        "errors": errors,
    }
    logger.info(f"[NER] {result}")
    return result
