"""
Tareas Celery para el scraping de redes sociales.
Programadas en celery_app.py (Beat):
  - Reddit  → cada 15 min
  - YouTube → cada 30 min
  - RSS     → cada 20 min
  - Twitter → cada 20 min
  - Cleanup → diario a las 3am
"""
import logging
from datetime import datetime, timedelta, timezone

from app.workers.celery_app import celery_app
from app.database import SessionLocal

logger = logging.getLogger(__name__)


def _run_scraper(scraper_class, task_name: str) -> dict:
    """Wrapper genérico: crea sesión DB, ejecuta scraper, cierra sesión."""
    db = SessionLocal()
    try:
        scraper = scraper_class(db)
        summary = scraper.scrape_all()
        total   = sum(summary.values())
        logger.info(f"[{task_name}] Completado. Total menciones nuevas: {total}. Detalle: {summary}")
        return {"status": "ok", "total": total, "detail": summary}
    except Exception as e:
        logger.error(f"[{task_name}] Error: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
    finally:
        db.close()


@celery_app.task(
    name="app.workers.tasks.scraping.scrape_reddit",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def scrape_reddit(self):
    from app.core.config import settings
    if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_CLIENT_SECRET:
        logger.warning("[Reddit] Credenciales no configuradas. Saltando tarea.")
        return {"status": "skipped", "reason": "credentials_missing"}
    try:
        from app.workers.scrapers.reddit import RedditScraper
        return _run_scraper(RedditScraper, "Reddit")
    except Exception as exc:
        logger.error(f"[Reddit] Fallo, reintentando: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.workers.tasks.scraping.scrape_youtube",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def scrape_youtube(self):
    from app.core.config import settings
    if not settings.YOUTUBE_API_KEY:
        logger.warning("[YouTube] API key no configurada. Saltando tarea.")
        return {"status": "skipped", "reason": "credentials_missing"}
    try:
        from app.workers.scrapers.youtube import YouTubeScraper
        return _run_scraper(YouTubeScraper, "YouTube")
    except Exception as exc:
        logger.error(f"[YouTube] Fallo, reintentando: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.workers.tasks.scraping.scrape_rss",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def scrape_rss(self):
    try:
        from app.workers.scrapers.rss import RSSScraper
        return _run_scraper(RSSScraper, "RSS")
    except Exception as exc:
        logger.error(f"[RSS] Fallo, reintentando: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.workers.tasks.scraping.scrape_twitter",
    bind=True,
    max_retries=2,
    default_retry_delay=180,
)
def scrape_twitter(self):
    """
    Scraping de Twitter/X usando twscrape.
    Requiere cuentas configuradas previamente:
        docker compose exec backend python scripts/add_twitter_account.py
    """
    try:
        from app.workers.scrapers.twitter import TwitterScraper
        return _run_scraper(TwitterScraper, "Twitter")
    except RuntimeError as exc:
        # twscrape no instalado o sin cuentas configuradas
        logger.warning(f"[Twitter] {exc}")
        return {"status": "skipped", "reason": str(exc)}
    except Exception as exc:
        logger.error(f"[Twitter] Fallo, reintentando: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(name="app.workers.tasks.scraping.cleanup_old_mentions")
def cleanup_old_mentions():
    """
    Elimina menciones con más de 12 meses de antigüedad.
    Se ejecuta diariamente a las 3am (configurado en celery_app.py).
    """
    db = SessionLocal()
    try:
        from app.models.mention import Mention
        cutoff = datetime.now(timezone.utc) - timedelta(days=365)
        deleted = db.query(Mention).filter(
            Mention.collected_at < cutoff
        ).delete(synchronize_session=False)
        db.commit()
        logger.info(f"[Cleanup] {deleted} menciones antiguas eliminadas (antes de {cutoff.date()})")
        return {"status": "ok", "deleted": deleted}
    except Exception as e:
        db.rollback()
        logger.error(f"[Cleanup] Error: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
    finally:
        db.close()
