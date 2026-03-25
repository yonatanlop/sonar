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
from app.workers.nlp.sentiment import analyze_sentiment
from app.workers.nlp.hate_speech import analyze_hate_speech
from app.models.mention import Mention

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

        # ── 3. Detección de discurso de odio ────────────────
        hate = analyze_hate_speech(text, lang)
        mention.hate_score      = Decimal(str(hate["hate_score"]))
        mention.is_hate_speech  = hate["is_hate"]

        # ── 4. Marcar como procesado ─────────────────────────
        mention.processed = True
        return True

    except Exception as e:
        logger.error(f"Error procesando mención {mention.id}: {e}", exc_info=True)
        return False


def process_batch(db: Session, mention_ids: list[str]) -> dict:
    """
    Procesa un lote de menciones por sus IDs.
    Retorna resumen del lote.
    """
    stats = {"processed": 0, "failed": 0, "not_found": 0}

    for mention_id in mention_ids:
        try:
            mention = db.query(Mention).filter(
                Mention.id == mention_id,
                Mention.processed == False,
            ).first()

            if not mention:
                stats["not_found"] += 1
                continue

            success = process_mention(mention)
            if success:
                stats["processed"] += 1
            else:
                stats["failed"] += 1

        except Exception as e:
            logger.error(f"Error inesperado en mención {mention_id}: {e}")
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
    for mention in orphans:
        process_mention(mention)

    try:
        db.commit()
        stats["processed"] += len(orphans)
    except Exception as e:
        db.rollback()
        logger.error(f"[NLP] Error en commit de huérfanas: {e}")
