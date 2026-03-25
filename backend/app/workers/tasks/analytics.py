"""
Tareas Celery para análisis estadístico e IA.
Programadas en celery_app.py (Beat):
  - detect_anomalies         → cada 30 min
  - generate_daily_summaries → diario a las 23:50
  - detect_topics            → cada hora
  - classify_bots            → cada 6 horas
  - compute_trends           → diario a las 00:30
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


@celery_app.task(
    name="app.workers.tasks.analytics.generate_daily_summaries",
    bind=True,
    max_retries=1,
    default_retry_delay=600,
)
def generate_daily_summaries(self):
    """
    Genera resúmenes diarios con Groq (Llama 3) para todas las entidades activas.
    Corre a las 23:50 cada día. Si GROQ_API_KEY no está configurada, se saltea.
    """
    db = SessionLocal()
    try:
        from app.workers.nlp.summarizer import run_daily_summaries
        return run_daily_summaries(db)
    except Exception as exc:
        logger.error(f"[Summary] Error en tarea: {exc}", exc_info=True)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    name="app.workers.tasks.analytics.detect_topics",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def detect_topics(self):
    """
    Agrupa las menciones recientes por temas usando TF-IDF + K-Means.
    Corre cada hora sobre los últimos 7 días de menciones.
    """
    db = SessionLocal()
    try:
        from app.workers.nlp.topics import run_topic_detection
        return run_topic_detection(db)
    except Exception as exc:
        logger.error(f"[Topics] Error en tarea: {exc}", exc_info=True)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    name="app.workers.tasks.analytics.classify_bots",
    bind=True,
    max_retries=1,
    default_retry_delay=600,
)
def classify_bots(self):
    """
    Clasifica cuentas no analizadas en las últimas 24h con el modelo ML de bots.
    Si el modelo pkl no existe usa heurísticas como fallback.
    """
    db = SessionLocal()
    try:
        from app.workers.nlp.bot_classifier import run_bot_classification
        return run_bot_classification(db)
    except Exception as exc:
        logger.error(f"[BotML] Error en tarea: {exc}", exc_info=True)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    name="app.workers.tasks.analytics.compute_trends",
    bind=True,
    max_retries=1,
    default_retry_delay=600,
)
def compute_trends(self):
    """
    Genera pronósticos de menciones para los próximos 7 días usando
    suavizado exponencial de Holt (con fallback a regresión lineal).
    Corre diariamente a las 00:30.
    """
    db = SessionLocal()
    try:
        from app.workers.analytics.trends import run_trend_forecasting
        return run_trend_forecasting(db)
    except Exception as exc:
        logger.error(f"[Trends] Error en tarea: {exc}", exc_info=True)
        raise self.retry(exc=exc)
    finally:
        db.close()
