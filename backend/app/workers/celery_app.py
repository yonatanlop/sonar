from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "sonar",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.tasks.scraping",
        "app.workers.tasks.nlp",
        "app.workers.tasks.alerts",
        "app.workers.tasks.analytics",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Bogota",
    enable_utc=True,
    task_track_started=True,
)

# ── Tareas programadas (Beat) ──────────────────────────────────
celery_app.conf.beat_schedule = {
    "scrape-reddit": {
        "task": "app.workers.tasks.scraping.scrape_reddit",
        "schedule": crontab(minute="*/15"),  # cada 15 min
    },
    "scrape-youtube": {
        "task": "app.workers.tasks.scraping.scrape_youtube",
        "schedule": crontab(minute="*/30"),  # cada 30 min
    },
    "scrape-rss": {
        "task": "app.workers.tasks.scraping.scrape_rss",
        "schedule": crontab(minute="*/20"),  # cada 20 min
    },
    # ── Phase 2: Twitter/X ────────────────────────────────────
    # Corre cada 20 min. Si no hay cuentas configuradas, la tarea
    # se saltea sin error (status: skipped).
    "scrape-twitter": {
        "task": "app.workers.tasks.scraping.scrape_twitter",
        "schedule": crontab(minute="*/20"),  # cada 20 min
    },
    "process-pending-mentions": {
        "task": "app.workers.tasks.nlp.process_pending_mentions",
        "schedule": crontab(minute="*/5"),   # cada 5 min
    },
    "evaluate-alert-rules": {
        "task": "app.workers.tasks.alerts.evaluate_alert_rules",
        "schedule": crontab(minute="*/5"),   # cada 5 min
    },
    "cleanup-old-mentions": {
        "task": "app.workers.tasks.scraping.cleanup_old_mentions",
        "schedule": crontab(hour=3, minute=0),  # diario a las 3am
    },
    # ── v2: Analytics ─────────────────────────────────────────────
    "detect-anomalies": {
        "task": "app.workers.tasks.analytics.detect_anomalies",
        "schedule": crontab(minute="*/30"),  # cada 30 min
    },
}
