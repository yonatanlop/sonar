import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.tasks.alerts.evaluate_alert_rules",
    soft_time_limit=120,
    max_retries=1,
)
def evaluate_alert_rules():
    """
    Tarea Celery Beat que se ejecuta cada 5 minutos.
    Evalúa todas las reglas activas y despacha notificaciones.
    """
    from app.workers.alert_engine import run_alert_engine

    try:
        summary = run_alert_engine()
        logger.info(f"evaluate_alert_rules completado: {summary}")
        return summary
    except Exception as exc:
        logger.error(f"evaluate_alert_rules falló: {exc}", exc_info=True)
        raise
