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
    Tras la detección, llama al agente de contexto para explicar
    las anomalías nuevas usando titulares RSS + Groq.
    """
    db = SessionLocal()
    try:
        from app.workers.analytics.anomaly import run_anomaly_detection
        result = run_anomaly_detection(db)

        # Explicar anomalías nuevas con contexto IA (no bloquea si Groq falla)
        if result.get("anomalies_detected", 0) > 0:
            try:
                from app.workers.agents.context_agent import run_context_analysis
                context_result = run_context_analysis(db)
                result["context"] = context_result
            except Exception as ctx_exc:
                logger.warning(f"[ContextAgent] No se pudo explicar anomalías: {ctx_exc}")

        return result
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
    name="app.workers.tasks.analytics.geocode_mentions",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def geocode_mentions(self):
    """
    Geocodifica la ubicación texto de los autores (user.location) a country_code ISO-2.
    Usa Nominatim (OpenStreetMap, gratuito, sin API key).
    Actualiza mentions.country_code para todas las menciones de cada autor.
    Rate limit: 1 req/s (respetado con sleep). Procesa máx 200 autores únicos por ciclo.
    """
    import time as _time

    db = SessionLocal()
    try:
        from app.models.mention import Mention
        from app.models.bot import AccountProfile
        from sqlalchemy import distinct, func

        # Autores únicos con menciones sin country_code y con location_text en su perfil
        subq = (
            db.query(Mention.author_ext_id)
            .filter(Mention.country_code.is_(None), Mention.author_ext_id.isnot(None))
            .distinct()
            .subquery()
        )
        profiles = (
            db.query(AccountProfile)
            .filter(
                AccountProfile.external_user_id.in_(db.query(subq)),
                AccountProfile.location_text.isnot(None),
                AccountProfile.location_text != "",
            )
            .limit(200)
            .all()
        )

        if not profiles:
            return {"status": "ok", "geocoded": 0, "skipped": 0}

        try:
            from geopy.geocoders import Nominatim
            from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
        except ImportError:
            return {"status": "skipped", "reason": "geopy no instalado"}

        geolocator = Nominatim(user_agent="sonar_monitor/1.0")
        geocoded = 0
        skipped  = 0

        for profile in profiles:
            try:
                location = geolocator.geocode(
                    profile.location_text,
                    exactly_one=True,
                    timeout=5,
                    language="en",
                    addressdetails=True,
                )
                if location and location.raw.get("address", {}).get("country_code"):
                    cc = location.raw["address"]["country_code"].upper()[:2]
                    # Actualizar todas las menciones de este autor sin country_code
                    db.query(Mention).filter(
                        Mention.author_ext_id == profile.external_user_id,
                        Mention.country_code.is_(None),
                    ).update({"country_code": cc}, synchronize_session=False)
                    db.commit()
                    geocoded += 1
                else:
                    skipped += 1

            except (GeocoderTimedOut, GeocoderUnavailable):
                skipped += 1
            except Exception as e:
                _cc = cc if 'cc' in locals() else 'N/A'
                logger.warning(f"[Geocode] Error en '{profile.location_text}' (cc={_cc}): {e}")
                skipped += 1

            _time.sleep(1.1)   # Nominatim: máx 1 req/s

        logger.info(f"[Geocode] Completado — geocoded: {geocoded}, skipped: {skipped}")
        return {"status": "ok", "geocoded": geocoded, "skipped": skipped}

    except Exception as exc:
        logger.error(f"[Geocode] Error: {exc}", exc_info=True)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    name="app.workers.tasks.analytics.refresh_dashboard_cache",
    bind=True,
    max_retries=0,
)
def refresh_dashboard_cache(self):
    """
    Pre-calcula el payload del dashboard y lo deja en caché (Redis) para que la
    carga del usuario sea instantánea. El cómputo pesado (agregar ~90K menciones)
    corre aquí en segundo plano, no en la petición web. Corre cada 4 min.
    Las agregaciones se resuelven en la DB (devuelven pocas filas), así que el
    footprint de memoria del worker es mínimo — compatible con la VM de 1GB.
    """
    db = SessionLocal()
    try:
        from app.api.v1.dashboard import compute_dashboard, dashboard_cache_set
        payload = compute_dashboard(db)
        dashboard_cache_set(payload)
        return {"status": "ok"}
    except Exception as exc:
        logger.error(f"[DashboardCache] Error: {exc}", exc_info=True)
        return {"status": "error", "error": str(exc)}
    finally:
        db.close()


@celery_app.task(
    name="app.workers.tasks.analytics.reclassify_relevance",
    bind=True,
    max_retries=0,
)
def reclassify_relevance(self, days: int = 30, dry_run: bool = True, batch: int = 500):
    """
    Reclasifica el histórico: marca is_relevant = false en las menciones cuyo texto
    NO cumple ninguna de sus keywords parametrizadas ni un alias de su entidad
    (el mismo criterio del post-filtro de ingesta). Solo pasa True → False y solo
    toca menciones que tienen keywords asociadas (sin keywords no se puede decidir).

    dry_run=True (por defecto) NO modifica nada: solo cuenta y devuelve una muestra.
    Ejecución manual (no está en el beat); procesa por lotes para cuidar la memoria.
    """
    from datetime import datetime, timedelta, timezone
    from collections import Counter
    from sqlalchemy import update
    from sqlalchemy.orm import selectinload
    from app.models.entity import EntityAlias
    from app.models.mention import Mention, SocialPlatform
    from app.workers.scrapers.base import text_matches_any_term

    db = SessionLocal()
    try:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        alias_cache: dict = {}

        def aliases_of(entity_id):
            if entity_id not in alias_cache:
                rows = db.query(EntityAlias.alias).filter(EntityAlias.entity_id == entity_id).all()
                alias_cache[entity_id] = [r[0] for r in rows]
            return alias_cache[entity_id]

        checked = no_keywords = flagged_total = 0
        by_platform: Counter = Counter()
        sample: list = []
        last_id = None

        while True:
            q = db.query(Mention).filter(
                Mention.is_relevant == True,  # noqa: E712
                Mention.collected_at >= since,
            )
            if last_id is not None:
                q = q.filter(Mention.id > last_id)
            rows = (
                q.options(selectinload(Mention.keywords))
                 .order_by(Mention.id).limit(batch).all()
            )
            if not rows:
                break
            last_id = rows[-1].id

            flagged_ids = []
            for m in rows:
                checked += 1
                if not m.keywords:
                    no_keywords += 1
                    continue
                if not text_matches_any_term(m.content, m.keywords, aliases_of(m.entity_id)):
                    flagged_ids.append(m.id)
                    by_platform[m.platform_id] += 1
                    if len(sample) < 10:
                        sample.append((m.content or "")[:90].replace("\n", " "))

            if flagged_ids:
                flagged_total += len(flagged_ids)
                if not dry_run:
                    db.execute(update(Mention).where(Mention.id.in_(flagged_ids)).values(is_relevant=False))
                    db.commit()
            db.expunge_all()

        names = {p.id: p.name for p in db.query(SocialPlatform).all()}
        return {
            "dry_run": dry_run, "days": days, "checked": checked,
            "sin_keywords_no_evaluadas": no_keywords,
            "marcadas_no_relevantes": flagged_total,
            "por_plataforma": {names.get(k, str(k)): v for k, v in by_platform.items()},
            "muestra": sample,
        }
    except Exception as exc:
        db.rollback()
        logger.error(f"[Relevance] Error: {exc}", exc_info=True)
        return {"status": "error", "error": str(exc)}
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
