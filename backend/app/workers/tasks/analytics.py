"""
Tareas Celery para análisis estadístico e IA.
Programadas en celery_app.py (Beat):
  - detect_anomalies → cada 30 min
"""
import logging

from app.workers.celery_app import celery_app
from app.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.tasks.analytics.detect_anomalies",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def detect_anomalies(self):
    """
    Detecta picos anómalos en volumen y sentimiento negativo
    usando Z-score sobre ventana de 7 días.
    """
    db = SessionLocal()
    try:
        from app.workers.analytics.anomaly import run_anomaly_detection
        return run_anomaly_detection(db)
    except Exception as exc:
        logger.error(f"[Anomaly] Error en tarea: {exc}", exc_info=True)
        raise self.retry(exc=exc)
    finally:
        db.close()
