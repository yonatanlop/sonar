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


@celery_app.task(name="app.workers.tasks.scraping.relogin_twitter_accounts")
def relogin_twitter_accounts():
    """
    Re-loguea todas las cuentas de Twitter para renovar la sesión activa.
    Programado cada 3 horas en celery_app.py para prevenir expiración de sesión.
    """
    import asyncio as _asyncio
    from app.workers.scrapers.twitter import TwitterScraper, _relogin_all_accounts

    try:
        db = SessionLocal()
        try:
            scraper = TwitterScraper(db)
            api = scraper._build_api()
            result = _asyncio.run(_relogin_all_accounts(api))
            logger.info(f"[Twitter] Re-login batch completado: {result}")
            return {"status": "ok", **result}
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[Twitter] Error en re-login: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@celery_app.task(name="app.workers.tasks.scraping.check_twitter_health")
def check_twitter_health():
    """
    Verifica si hay cuentas de Twitter activas en el pool.
    Si todas están bloqueadas o inactivas, envía alerta al admin por Telegram
    con los comandos PowerShell exactos para renovar las cookies.
    Programado cada hora en celery_app.py.
    """
    import asyncio as _asyncio

    try:
        from app.workers.scrapers.twitter import TwitterScraper
        from app.notifications.telegram import send_admin_message
        from app.notifications.whatsapp import send_admin_whatsapp

        db = SessionLocal()
        try:
            scraper = TwitterScraper(db)
            api = scraper._build_api()
            accounts = _asyncio.run(api.pool.get_all())
        finally:
            db.close()

        if not accounts:
            logger.warning("[Twitter] Health check: sin cuentas registradas en el pool.")
            send_admin_message(
                "⚠️ *SONAR — Twitter sin cuentas*\n\n"
                "No hay ninguna cuenta de Twitter registrada en el pool\\.\n\n"
                "Para agregar una cuenta, ejecuta en PowerShell:\n"
                "```\n"
                "docker exec -it sonar_worker python /app/scripts/add_twitter_account.py "
                "--username TU_USUARIO --email TU@EMAIL.COM --password TU_CONTRASEÑA\n"
                "```"
            )
            return {"status": "warning", "reason": "no_accounts"}

        active = [a for a in accounts if getattr(a, "active", True)]
        if active:
            logger.info(f"[Twitter] Health check OK — {len(active)}/{len(accounts)} cuentas activas.")
            return {"status": "ok", "active": len(active), "total": len(accounts)}

        # Todas las cuentas bloqueadas → alerta por Telegram + WhatsApp
        usernames = ", ".join([a.username for a in accounts])
        logger.warning(f"[Twitter] Health check: 0/{len(accounts)} cuentas activas ({usernames}). Enviando alerta admin.")

        telegram_msg = (
            "🚨 *SONAR — Twitter cookies inactivas*\n\n"
            f"Todas las cuentas están bloqueadas: {usernames}\n\n"
            "*Opción A — Re\\-login manual:*\n"
            "```powershell\n"
            "docker exec -it sonar_worker python /app/scripts/add_twitter_account.py `\n"
            "  --username TU_USUARIO `\n"
            "  --email TU@EMAIL.COM `\n"
            "  --password TU_CONTRASEÑA\n"
            "```\n\n"
            "*Opción B — Reiniciar workers:*\n"
            "```powershell\n"
            "docker compose restart worker beat\n"
            "```"
        )
        whatsapp_msg = (
            f"🚨 SONAR - Twitter inactivo\n"
            f"Cuentas bloqueadas: {usernames}\n\n"
            f"Ejecuta en PowerShell:\n"
            f"docker compose restart worker beat\n\n"
            f"O renueva cookies con add_twitter_account.py"
        )
        send_admin_message(telegram_msg)
        send_admin_whatsapp(whatsapp_msg)
        return {"status": "warning", "active": 0, "total": len(accounts)}

    except Exception as e:
        logger.error(f"[Twitter] Error en health check: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@celery_app.task(
    name="app.workers.tasks.scraping.scrape_instagram",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def scrape_instagram(self):
    """
    Scraping de Instagram usando instagrapi con pool de cuentas.
    Requiere al menos IG_ACCOUNT_1_USERNAME y IG_ACCOUNT_1_PASSWORD en .env
    """
    try:
        from app.workers.scrapers.instagram import InstagramScraper
        return _run_scraper(InstagramScraper, "Instagram")
    except RuntimeError as exc:
        logger.warning(f"[Instagram] {exc}")
        return {"status": "skipped", "reason": str(exc)}
    except Exception as exc:
        logger.error(f"[Instagram] Fallo, reintentando: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.workers.tasks.scraping.scrape_facebook",
    bind=True,
    max_retries=1,
    default_retry_delay=600,
)
def scrape_facebook(self):
    """
    Scraping de Facebook usando facebook-scraper con cookies de sesión.
    Requiere FB_COOKIES_FILE apuntando a cookies exportadas de facebook.com.
    """
    try:
        from app.workers.scrapers.facebook import FacebookScraper
        return _run_scraper(FacebookScraper, "Facebook")
    except RuntimeError as exc:
        logger.warning(f"[Facebook] {exc}")
        return {"status": "skipped", "reason": str(exc)}
    except Exception as exc:
        logger.error(f"[Facebook] Fallo, reintentando: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.workers.tasks.scraping.scrape_twitter_feeds",
    bind=True,
    max_retries=2,
    default_retry_delay=180,
)
def scrape_twitter_feeds(self):
    """
    Scraping de los feeds de Twitter Explorer (@usuarios, #hashtags, keywords).
    Lee los TwitterFeed activos y guarda tweets como menciones en la BD.
    """
    import asyncio as _asyncio

    try:
        from app.workers.scrapers.twitter import scrape_feeds
        db = SessionLocal()
        try:
            result = _asyncio.run(scrape_feeds(db))
            db.commit()
            logger.info(f"[TwitterFeeds] Completado: {result}")
            return {"status": "ok", **result}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except RuntimeError as exc:
        logger.warning(f"[TwitterFeeds] {exc}")
        return {"status": "skipped", "reason": str(exc)}
    except Exception as exc:
        logger.error(f"[TwitterFeeds] Fallo, reintentando: {exc}", exc_info=True)
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
