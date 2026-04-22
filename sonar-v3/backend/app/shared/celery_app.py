from celery import Celery
from celery.schedules import crontab

from app.shared.config import settings

celery_app = Celery(
    "sonar-v3",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.collection_tasks",
        "app.tasks.intelligence_tasks",
        "app.tasks.alerting_tasks",
        "app.tasks.reporting_tasks",
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

celery_app.conf.beat_schedule = {
    # ── Scrapers ──────────────────────────────────────────────────
    "scrape-reddit": {
        "task": "app.tasks.collection_tasks.scrape_reddit",
        "schedule": crontab(minute="*/15"),
    },
    "scrape-youtube": {
        "task": "app.tasks.collection_tasks.scrape_youtube",
        "schedule": crontab(minute="*/30"),
    },
    "scrape-rss": {
        "task": "app.tasks.collection_tasks.scrape_rss",
        "schedule": crontab(minute="*/20"),
    },
    "scrape-twitter": {
        "task": "app.tasks.collection_tasks.scrape_twitter",
        "schedule": crontab(minute="0,40"),
    },
    "scrape-instagram": {
        "task": "app.tasks.collection_tasks.scrape_instagram",
        "schedule": crontab(minute="*/30"),
    },
    "scrape-facebook": {
        "task": "app.tasks.collection_tasks.scrape_facebook",
        "schedule": crontab(minute=0),
    },
    "scrape-twitter-feeds": {
        "task": "app.tasks.collection_tasks.scrape_twitter_feeds",
        "schedule": crontab(minute="20"),
    },
    "relogin-twitter": {
        "task": "app.tasks.collection_tasks.relogin_twitter_accounts",
        "schedule": crontab(minute=0, hour="*/3"),
    },
    "check-twitter-health": {
        "task": "app.tasks.collection_tasks.check_twitter_health",
        "schedule": crontab(minute=30),
    },
    "cleanup-old-mentions": {
        "task": "app.tasks.collection_tasks.cleanup_old_mentions",
        "schedule": crontab(hour=3, minute=0),
    },
    # ── NLP / Intelligence ────────────────────────────────────────
    "process-pending-mentions": {
        "task": "app.tasks.intelligence_tasks.process_pending_mentions",
        "schedule": crontab(minute="*/5"),
    },
    "extract-ner": {
        "task": "app.tasks.intelligence_tasks.extract_ner",
        "schedule": crontab(minute=30),
    },
    "generate-embeddings": {
        "task": "app.tasks.intelligence_tasks.generate_embeddings",
        "schedule": crontab(minute="*/30"),
    },
    "analyze-visual-mentions": {
        "task": "app.tasks.intelligence_tasks.analyze_visual_mentions",
        "schedule": crontab(minute="*/30"),
    },
    "detect-anomalies": {
        "task": "app.tasks.intelligence_tasks.detect_anomalies",
        "schedule": crontab(minute="*/30"),
    },
    "generate-daily-summaries": {
        "task": "app.tasks.intelligence_tasks.generate_daily_summaries",
        "schedule": crontab(hour=23, minute=50),
    },
    "detect-topics": {
        "task": "app.tasks.intelligence_tasks.detect_topics",
        "schedule": crontab(minute=0),
    },
    "classify-bots": {
        "task": "app.tasks.intelligence_tasks.classify_bots",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "geocode-mentions": {
        "task": "app.tasks.intelligence_tasks.geocode_mentions",
        "schedule": crontab(minute="*/30"),
    },
    "compute-trends": {
        "task": "app.tasks.intelligence_tasks.compute_trends",
        "schedule": crontab(hour=0, minute=30),
    },
    # ── Alertas ───────────────────────────────────────────────────
    "evaluate-alert-rules": {
        "task": "app.tasks.alerting_tasks.evaluate_alert_rules",
        "schedule": crontab(minute="*/5"),
    },
}
