from celery import Celery
from celery.schedules import crontab

from app.core.config import settings
import app.models  # noqa: F401 — registra todos los mappers ORM antes de que el worker procese tareas

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
    # Enruta scrape_facebook a una queue separada para que pueda
    # ser consumida por un worker con IP residencial (no datacenter)
    task_routes={
        "app.workers.tasks.scraping.scrape_facebook":       {"queue": "facebook"},
        "app.workers.tasks.scraping.scrape_facebook_feeds": {"queue": "facebook"},
        "app.workers.tasks.scraping.scrape_tiktok":         {"queue": "tiktok"},
        "app.workers.tasks.scraping.scrape_tiktok_feeds":   {"queue": "tiktok"},
    },
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
    # Corre cada 5 min. El task decide si ejecutar según cuentas activas:
    #   1 cuenta → cada 30 min | 2 → 15 min | 3 → 10 min | 4+ → 5 min
    "scrape-twitter": {
        "task": "app.workers.tasks.scraping.scrape_twitter",
        "schedule": crontab(minute="*/5"),
    },
    # ── Facebook e Instagram ──────────────────────────────────────
    "scrape-instagram": {
        "task": "app.workers.tasks.scraping.scrape_instagram",
        "schedule": crontab(minute="*/30"),  # cada 30 min
    },
    "scrape-facebook": {
        "task": "app.workers.tasks.scraping.scrape_facebook",
        "schedule": crontab(minute=0, hour="*/2"),  # cada 2 horas (menos agresivo, evita rate-limit)
    },
    # YouTube Explorer: canales asignados con keywords
    "scrape-youtube-channels": {
        "task": "app.workers.tasks.scraping.scrape_youtube_channels",
        "schedule": crontab(minute="*/30"),  # cada 30 min, offset de scrape-youtube
    },
    # Twitter Explorer: feeds de @usuarios, #hashtags y keywords (incluye Rizoma)
    # Cada 10 min para reducir latencia de detección a ~10 min.
    "scrape-twitter-feeds": {
        "task": "app.workers.tasks.scraping.scrape_twitter_feeds",
        "schedule": crontab(minute="*/10"),  # cada 10 min
    },
    # Instagram Explorer: feeds por hashtag o cuenta
    "scrape-instagram-feeds": {
        "task": "app.workers.tasks.scraping.scrape_instagram_feeds",
        "schedule": crontab(minute="*/30"),  # cada 30 min
    },
    # Facebook Explorer: feeds por palabra clave o página (worker residencial)
    "scrape-facebook-feeds": {
        "task": "app.workers.tasks.scraping.scrape_facebook_feeds",
        "schedule": crontab(minute=30),      # cada hora en el minuto 30 (offset de scrape-facebook)
    },
    # TikTok Explorer: feeds por keyword, hashtag o creador (worker residencial)
    "scrape-tiktok-feeds": {
        "task": "app.workers.tasks.scraping.scrape_tiktok_feeds",
        "schedule": crontab(minute="*/30"),  # cada 30 min
    },
    # Re-login preventivo cada 3 horas para renovar sesión de twscrape
    "relogin-twitter": {
        "task": "app.workers.tasks.scraping.relogin_twitter_accounts",
        "schedule": crontab(minute=0, hour="*/3"),  # cada 3 horas en punto
    },
    # Health check cada hora: si 0 cuentas activas → alerta Telegram al admin
    "check-twitter-health": {
        "task": "app.workers.tasks.scraping.check_twitter_health",
        "schedule": crontab(minute=30),  # cada hora en el minuto 30
    },
    "process-pending-mentions": {
        "task": "app.workers.tasks.nlp.process_pending_mentions",
        "schedule": crontab(minute="*/5"),   # cada 5 min
    },
    "extract-ner": {
        "task": "app.workers.tasks.nlp.extract_ner",
        "schedule": crontab(minute=30),      # cada hora en el minuto 30
    },
    "generate-embeddings": {
        "task": "app.workers.tasks.nlp.generate_embeddings",
        "schedule": crontab(minute="*/30"),  # cada 30 min
    },
    # ── Módulo 7: Reconocimiento Visual ───────────────────────────
    # Solo activo si FACE_RECOGNITION_ENABLED=true en .env
    "analyze-visual-mentions": {
        "task": "app.workers.tasks.nlp.analyze_visual_mentions",
        "schedule": crontab(minute="*/30"),  # cada 30 min
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
    "generate-daily-summaries": {
        "task": "app.workers.tasks.analytics.generate_daily_summaries",
        "schedule": crontab(hour=23, minute=50),  # diario a las 23:50
    },
    "detect-topics": {
        "task": "app.workers.tasks.analytics.detect_topics",
        "schedule": crontab(minute=0),  # cada hora en punto
    },
    "classify-bots": {
        "task": "app.workers.tasks.analytics.classify_bots",
        "schedule": crontab(minute=15),  # cada hora (1000 cuentas por prioridad: monitoreadas primero)
    },
    "detect-coordination": {
        "task": "app.workers.tasks.analytics.detect_coordination",
        "schedule": crontab(minute=40, hour="*/3"),  # cada 3 horas
    },
    "geocode-mentions": {
        "task": "app.workers.tasks.analytics.geocode_mentions",
        "schedule": crontab(minute="*/30"),  # cada 30 min
    },
    "compute-trends": {
        "task": "app.workers.tasks.analytics.compute_trends",
        "schedule": crontab(hour=0, minute=30),  # diario a las 00:30
    },
    # Pre-calcula el payload del dashboard y lo deja en caché (Redis) para que
    # la carga del usuario sea instantánea (el cómputo pesado corre aquí, no en
    # la petición web).
    "refresh-dashboard-cache": {
        "task": "app.workers.tasks.analytics.refresh_dashboard_cache",
        "schedule": crontab(minute="*/4"),  # cada 4 min
    },
    # ── Módulo 8: Búsqueda Inversa — cómputo de pHash incremental ────
    "compute-image-phash": {
        "task": "app.workers.tasks.nlp.compute_image_phash",
        "schedule": crontab(minute="*/30"),
    },
    # ── Búsqueda Twitter por Keyword/Hashtag ──────────────────────
    # activate-twitter-keyword-search: activa automáticamente a las 8 PM hora Colombia
    # timezone="America/Bogota" en celery_app.conf → crontab(hour=20) = 8 PM COT exacto
    "activate-twitter-keyword-search": {
        "task": "app.workers.tasks.scraping.activate_twitter_keyword_search",
        "schedule": crontab(hour=20, minute=0),
    },
    # search-twitter-keywords: runda recurrente cada 20 min, no-op si is_active=False
    "search-twitter-keywords": {
        "task": "app.workers.tasks.scraping.search_twitter_keywords",
        "schedule": crontab(minute="*/20"),
    },
    # Detecta automáticamente cuando una cuenta de respuesta interactuó con un post
    "check-reply-interactions": {
        "task": "app.workers.tasks.scraping.check_reply_account_interactions",
        "schedule": crontab(minute="*/30"),
    },
    # ── TikTok ───────────────────────────────────────────────────
    "scrape-tiktok": {
        "task": "app.workers.tasks.scraping.scrape_tiktok",
        "schedule": crontab(minute="*/30"),  # cada 30 min
    },
}


# ── Caducidad de las tareas programadas ────────────────────────
# Beat encola cada tarea aunque la anterior siga sin ejecutarse. Con un solo worker (concurrencia 1) y un
# scraping de Twitter que puede durar más que su intervalo, la cola crecía sin límite (41 000 tareas en
# septiembre de 2026): los resúmenes diarios, anomalías, etc. quedaban al final de la fila y no se ejecutaban.
# Ahora cada tarea caduca a los 2 períodos de su programación: si el worker no llegó a tiempo, se descarta y
# corre la siguiente; así la cola no se acumula.
def _cyclic_min_gap(values, cycle):
    v = sorted(values)
    if len(v) < 2:
        return cycle
    return min([b - a for a, b in zip(v, v[1:])] + [v[0] + cycle - v[-1]])


def _period_seconds(cron) -> int:
    """Período (en segundos) entre dos ejecuciones consecutivas de un crontab."""
    if len(cron.day_of_week) < 7 or len(cron.day_of_month) < 31 or len(cron.month_of_year) < 12:
        return 7 * 86400
    if len(cron.hour) == 24:
        return _cyclic_min_gap(cron.minute, 60) * 60
    return _cyclic_min_gap(cron.hour, 24) * 3600


for _entry in celery_app.conf.beat_schedule.values():
    _entry.setdefault("options", {})["expires"] = _period_seconds(_entry["schedule"]) * 2
