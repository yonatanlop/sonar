"""
Tareas Celery para procesamiento NLP de menciones.
Programadas en celery_app.py (Beat):
  - process_pending_mentions → cada 5 min
  - extract_ner              → cada hora
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


@celery_app.task(
    name="app.workers.tasks.nlp.extract_ner",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
    soft_time_limit=300,
    time_limit=360,
)
def extract_ner(self):
    """
    Extrae entidades nombradas (PER/ORG/LOC) de menciones recientes usando spaCy.
    Corre cada hora sobre los últimos 7 días de menciones procesadas sin NER.
    """
    db = SessionLocal()
    try:
        from app.workers.nlp.ner import run_ner_extraction
        result = run_ner_extraction(db)
        logger.info(f"[NER Task] {result}")
        return result
    except Exception as exc:
        logger.error(f"[NER Task] Fallo: {exc}", exc_info=True)
        raise self.retry(exc=exc)
    finally:
        db.close()
