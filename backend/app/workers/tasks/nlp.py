"""
Tarea Celery para el procesamiento NLP de menciones.
Programada en celery_app.py (Beat): cada 5 minutos.

Lee la cola Redis 'nlp:pending' y aplica el pipeline completo:
  1. Detección de idioma
  2. Análisis de sentimiento
  3. Detección de discurso de odio
  4. Actualiza mención en BD (sentiment_label, sentiment_score, hate_score, processed)
"""
import logging

from app.workers.celery_app import celery_app
from app.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.tasks.nlp.process_pending_mentions",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=240,   # máximo 4 minutos por ejecución
    time_limit=300,
)
def process_pending_mentions(self):
    """
    Procesa todas las menciones pendientes en la cola NLP.
    Se ejecuta cada 5 minutos vía Celery Beat.
    """
    db = SessionLocal()
    try:
        from app.workers.nlp.pipeline import run_nlp_pipeline
        stats = run_nlp_pipeline(db)

        logger.info(
            f"[NLP Task] Completado — "
            f"{stats['processed']} procesadas, "
            f"{stats['failed']} errores, "
            f"{stats['batches']} lotes"
        )
        return {"status": "ok", **stats}

    except Exception as exc:
        db.rollback()
        logger.error(f"[NLP Task] Fallo: {exc}", exc_info=True)
        raise self.retry(exc=exc)
    finally:
        db.close()
