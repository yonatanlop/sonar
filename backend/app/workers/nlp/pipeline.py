"""
Pipeline NLP orquestador.

Flujo por mención:
  1. Detectar idioma (langdetect / lingua-py)
  2. Analizar sentimiento (modelo según idioma)
  3. Detectar discurso de odio
  4. Actualizar mención en BD con todos los scores
  5. Marcar como processed = True

Procesamiento en lotes:
  - Lee hasta BATCH_SIZE IDs de la cola Redis 'nlp:pending'
  - Procesa en batch y hace un solo commit por batch
  - Si un mención falla, continúa con las demás
"""
import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.workers.nlp.language_detector import detect_language
from app.workers.nlp.sentiment import analyze_sentiment, analyze_sentiment_groq
from app.workers.nlp.hate_speech import analyze_hate_speech
from app.workers.nlp.urgency import compute_urgency_score
from app.models.mention import Mention
from app.models.entity import Entity, EntityType

_COSINE_THRESHOLD = 0.92   # similitud mínima para considerarlo duplicado


def _is_near_duplicate(mention: Mention, limit: int = 1000) -> bool:
    """
    Compara el embedding de la mención contra las últimas `limit` menciones
    con embedding de la misma entidad, excluyendo ella misma.
    Devuelve True si hay otra mención con similitud coseno >= 0.92.
    Requiere que la mención tenga embedding y que pgvector esté disponible.
    """
    try:
        from pgvector.sqlalchemy import cosine_distance
        from sqlalchemy import inspect
        # Necesitamos la sesión — se obtiene a través del objeto instanciado
        session = inspect(mention).session
        if session is None:
            return False

        candidate = (
            session.query(Mention)
            .filter(
                Mention.entity_id == mention.entity_id,
                Mention.id != mention.id,
                Mention.embedding.isnot(None),
                Mention.is_duplicate == False,
            )
            .order_by(cosine_distance(Mention.embedding, mention.embedding))
            .first()
        )
        if candidate is None:
            return False

        # cosine_distance devuelve 0 = idéntico, 2 = opuesto
        # similitud coseno = 1 - distancia
        dist = session.query(
            cosine_distance(Mention.embedding, mention.embedding)
        ).filter(Mention.id == candidate.id).scalar()

        return dist is not None and (1.0 - float(dist)) >= _COSINE_THRESHOLD

    except Exception as exc:
        logger.debug(f"Dedup check omitido para {mention.id}: {exc}")
        return False

logger = logging.getLogger(__name__)

BATCH_SIZE = 20   # menciones por lote


def process_mention(mention: Mention) -> bool:
    """
    Aplica el pipeline NLP completo a una sola mención.
    Modifica el objeto mention en-place.
    Retorna True si fue procesada exitosamente.
    """
    text = mention.content_clean or mention.content
    if not text or len(text.strip()) < 5:
        mention.processed = True
        mention.language  = mention.language or "es"
        mention.sentiment_label = "neutral"
        mention.sentiment_score = Decimal("0.500")
        return True

    try:
        # ── 1. Detección de idioma ──────────────────────────
        lang = mention.language  # si ya fue detectado por el scraper, respetar
        if not lang:
            lang = detect_language(text)
            mention.language = lang

        # ── 2. Análisis de sentimiento ──────────────────────
        sentiment = analyze_sentiment(text, lang)
        mention.sentiment_label = sentiment["label"]
        mention.sentiment_score = Decimal(str(sentiment["score"]))

        # ── 2b. Segunda pasada Groq (neutral con baja confianza) ─────
        if sentiment["label"] == "neutral" and float(sentiment["score"]) < 0.70:
            try:
                from sqlalchemy import inspect as sa_inspect
                session = sa_inspect(mention).session
                entity = session.query(Entity).filter(Entity.id == mention.entity_id).first() if session else None
                entity_name = entity.name if entity else ""
                groq_result = analyze_sentiment_groq(text, entity_name)
                if groq_result and groq_result["label"] != "neutral":
                    mention.sentiment_label = groq_result["label"]
                    mention.sentiment_score = Decimal(str(groq_result["score"]))
                    logger.debug("Groq reclasificó %s: neutral→%s", mention.id, groq_result["label"])
            except Exception as exc:
                logger.debug("Groq second pass skipped for %s: %s", mention.id, exc)

        # ── 3. Detección de discurso de odio ────────────────
        hate = analyze_hate_speech(text, lang)
        mention.hate_score      = Decimal(str(hate["hate_score"]))
        mention.is_hate_speech  = hate["is_hate"]

        # ── 4. Urgency Score ─────────────────────────────────
        mention.urgency_score = compute_urgency_score(
            sentiment_label=mention.sentiment_label,
            sentiment_score=float(mention.sentiment_score) if mention.sentiment_score else None,
            hate_score=float(mention.hate_score) if mention.hate_score else None,
            is_hate_speech=mention.is_hate_speech,
            reach=mention.reach or 0,
        )

        # ── 5. Deduplicación por embedding (si ya tiene embedding) ──
        if mention.embedding is not None:
            mention.is_duplicate = _is_near_duplicate(mention)

        # ── 6. Marcar como procesado ─────────────────────────
        mention.processed = True
        return True

    except Exception as e:
        logger.error(f"Error procesando mención {mention.id}: {e}", exc_info=True)
        return False


def _feed_entity_ids(db: Session, entity_ids: set) -> set:
    """Retorna el subconjunto de entity_ids que pertenecen al tipo 'Monitor Twitter'."""
    if not entity_ids:
        return set()
    rows = (
        db.query(Entity.id)
        .join(EntityType, Entity.entity_type_id == EntityType.id)
        .filter(EntityType.name == "Monitor Twitter", Entity.id.in_(entity_ids))
        .all()
    )
    return {r[0] for r in rows}


def process_batch(db: Session, mention_ids: list[str]) -> dict:
    """
    Procesa un lote de menciones por sus IDs.
    Retorna resumen del lote.
    """
    stats = {"processed": 0, "failed": 0, "not_found": 0}

    # Cargar menciones del lote
    mentions = (
        db.query(Mention)
        .filter(Mention.id.in_(mention_ids), Mention.processed == False)
        .all()
    )
    found_ids = {str(m.id) for m in mentions}
    stats["not_found"] += len(mention_ids) - len(found_ids)

    # Identificar cuáles son de feeds (no requieren sentimiento)
    entity_ids = {m.entity_id for m in mentions}
    feed_ids   = _feed_entity_ids(db, entity_ids)

    for mention in mentions:
        try:
            if mention.entity_id in feed_ids:
                # Feed del Explorer: solo detectar idioma, no analizar sentimiento
                text = mention.content_clean or mention.content
                if text and not mention.language:
                    mention.language = detect_language(text)
                mention.processed = True
                stats["processed"] += 1
                continue

            success = process_mention(mention)
            if success:
                stats["processed"] += 1
            else:
                stats["failed"] += 1

        except Exception as e:
            logger.error(f"Error inesperado en mención {mention.id}: {e}")
            stats["failed"] += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error en commit del lote NLP: {e}")

    return stats


def run_nlp_pipeline(db: Session) -> dict:
    """
    Lee la cola Redis 'nlp:pending' y procesa en lotes.
    Llamado por la tarea Celery cada 5 minutos.
    """
    import redis as redis_lib
    from app.core.config import settings

    r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

    total_stats = {"processed": 0, "failed": 0, "not_found": 0, "batches": 0}
    queue_key   = "nlp:pending"

    while True:
        # Leer hasta BATCH_SIZE IDs de la cola (FIFO: rpop procesa los más antiguos)
        batch_ids = []
        for _ in range(BATCH_SIZE):
            item = r.rpop(queue_key)
            if item is None:
                break
            batch_ids.append(item)

        if not batch_ids:
            break  # cola vacía

        batch_stats = process_batch(db, batch_ids)
        total_stats["processed"] += batch_stats["processed"]
        total_stats["failed"]    += batch_stats["failed"]
        total_stats["not_found"] += batch_stats["not_found"]
        total_stats["batches"]   += 1

        logger.info(
            f"[NLP] Lote {total_stats['batches']}: "
            f"{batch_stats['processed']} OK, "
            f"{batch_stats['failed']} errores, "
            f"{batch_stats['not_found']} no encontradas"
        )

    # También procesar menciones sin procesar que no estén en la cola
    # (por si el worker se reinició y perdió items de Redis)
    _process_orphan_mentions(db, total_stats)

    return total_stats


def _process_orphan_mentions(db: Session, stats: dict, limit: int = 100):
    """
    Procesa menciones con processed=False que no estén en la cola Redis.
    Failsafe para no perder menciones.
    """
    orphans = (db.query(Mention)
               .filter(Mention.processed == False)
               .limit(limit)
               .all())

    if not orphans:
        return

    logger.info(f"[NLP] Procesando {len(orphans)} menciones huérfanas")
    entity_ids = {m.entity_id for m in orphans}
    feed_ids   = _feed_entity_ids(db, entity_ids)

    for mention in orphans:
        if mention.entity_id in feed_ids:
            text = mention.content_clean or mention.content
            if text and not mention.language:
                mention.language = detect_language(text)
            mention.processed = True
        else:
            process_mention(mention)

    try:
        db.commit()
        stats["processed"] += len(orphans)
    except Exception as e:
        db.rollback()
        logger.error(f"[NLP] Error en commit de huérfanas: {e}")
