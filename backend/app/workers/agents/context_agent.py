"""
Agente de Contexto — Módulo 5.1 v2

Cuando se detecta una anomalía estadística, este agente:
  1. Obtiene los feeds RSS configurados para el país de la entidad + fuentes globales.
  2. Descarga los titulares de las últimas 24 h y filtra los relevantes para la entidad.
  3. Envía al LLM (Groq): "¿Por qué podría estar aumentando {entidad}? Contexto: {titulares}"
  4. Guarda la explicación en `anomalies.context_explanation`.

Si GROQ_API_KEY no está configurada, el módulo se saltea silenciosamente.
Máximo 3 feeds por llamada para mantener latencia < 10 s.
"""
import logging
import time
from datetime import datetime, timezone, timedelta

import feedparser

logger = logging.getLogger(__name__)

MAX_FEEDS          = 3    # límite de feeds a consultar por anomalía
MAX_HEADLINES      = 12   # titulares máximos a enviar al prompt
MAX_HEADLINE_LEN   = 160  # caracteres por titular
FEED_TIMEOUT_SECS  = 5    # timeout por feed


# ── RSS sources (importadas desde el scraper existente) ───────────

def _get_feeds_for_entity(entity) -> list[tuple[str, str, str]]:
    """
    Retorna lista de (nombre, url, idioma) para la entidad.
    Combina fuentes globales + fuentes del país de la entidad.
    """
    try:
        from app.workers.scrapers.rss import RSS_SOURCES, GLOBAL_SOURCES
        sources = list(GLOBAL_SOURCES)
        if entity.country_code and entity.country_code in RSS_SOURCES:
            sources = RSS_SOURCES[entity.country_code] + sources
        return sources[:MAX_FEEDS]
    except Exception:
        # Fuentes de emergencia si el import falla
        return [
            ("BBC Mundo",    "https://feeds.bbci.co.uk/mundo/rss.xml", "es"),
            ("CNN Español",  "https://cnnespanol.cnn.com/feed/",        "es"),
            ("DW Español",   "https://rss.dw.com/rdf/rss-spa-all",     "es"),
        ][:MAX_FEEDS]


def _fetch_headlines(feeds: list[tuple], max_age_hours: int = 24) -> list[dict]:
    """
    Descarga feeds y retorna titulares recientes como:
    [{ title, summary, source, published }]
    """
    headlines = []
    cutoff    = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    for name, url, _lang in feeds:
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "SONAR-ContextAgent/2.0"})
            for entry in feed.entries[:10]:
                # Parsear fecha de publicación
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    except Exception:
                        pass

                if published and published < cutoff:
                    continue  # demasiado antiguo

                title   = getattr(entry, "title",   "").strip()[:MAX_HEADLINE_LEN]
                summary = getattr(entry, "summary", "").strip()[:MAX_HEADLINE_LEN]
                if title:
                    headlines.append({
                        "title":     title,
                        "summary":   summary,
                        "source":    name,
                        "published": published.isoformat() if published else None,
                    })
            time.sleep(0.5)  # cortesía entre feeds
        except Exception as exc:
            logger.debug(f"[ContextAgent] Feed {name} falló: {exc}")

    return headlines


def _filter_relevant(headlines: list[dict], entity) -> list[dict]:
    """
    Retorna los titulares que mencionan la entidad o alguna de sus keywords.
    Matching case-insensitive sobre title + summary.
    """
    search_terms = [entity.name.lower()]
    for kw in (entity.keywords or []):
        if hasattr(kw, "keyword") and kw.keyword:
            search_terms.append(kw.keyword.lower())
    # También considerar aliases
    for alias in (entity.aliases or []):
        if hasattr(alias, "alias") and alias.alias:
            search_terms.append(alias.alias.lower())

    relevant = []
    for h in headlines:
        text = (h["title"] + " " + h["summary"]).lower()
        if any(term in text for term in search_terms):
            relevant.append(h)

    return relevant[:MAX_HEADLINES]


def _call_groq(entity_name: str, metric: str, z_score: float, headlines: list[dict]) -> str | None:
    """
    Llama a Groq (Llama 3) para generar una explicación de contexto.
    Retorna el texto generado o None si hay error.
    """
    try:
        import groq
        from app.core.config import settings

        if not settings.GROQ_API_KEY:
            return None

        metric_label = (
            "el volumen de menciones" if metric == "volume"
            else "el porcentaje de menciones negativas"
        )

        if headlines:
            headlines_block = "\n".join(
                f"- [{h['source']}] {h['title']}"
                + (f": {h['summary'][:80]}" if h.get("summary") else "")
                for h in headlines
            )
            context_note = f"Titulares relevantes de las últimas 24 h:\n{headlines_block}"
        else:
            context_note = "No se encontraron titulares recientes relacionados con la entidad en los feeds monitoreados."

        prompt = (
            f"Eres un analista de reputación. Se detectó una anomalía estadística en el monitoreo "
            f"de «{entity_name}»: {metric_label} está inusualmente elevado "
            f"(z-score = {z_score:.1f}, es decir, {z_score:.1f} desviaciones estándar sobre la media de 7 días).\n\n"
            f"{context_note}\n\n"
            f"En 2-3 oraciones en español (sin markdown, sin viñetas), explica brevemente "
            f"cuál podría ser la causa de este pico. Si los titulares no son claramente relevantes, "
            f"menciona las hipótesis más probables basándote en el contexto general."
        )

        client   = groq.Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=settings.SUMMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()

    except Exception as exc:
        logger.error(f"[ContextAgent] Groq falló: {exc}", exc_info=True)
        return None


# ── Función principal ─────────────────────────────────────────────

def explain_anomaly(db, anomaly) -> bool:
    """
    Genera y guarda la explicación de contexto para una anomalía.
    Retorna True si se generó explicación, False si se saltó.
    """
    from app.core.config import settings
    if not settings.GROQ_API_KEY:
        return False

    from app.models.entity import Entity
    entity = db.query(Entity).filter(Entity.id == anomaly.entity_id).first()
    if not entity:
        return False

    try:
        feeds      = _get_feeds_for_entity(entity)
        headlines  = _fetch_headlines(feeds, max_age_hours=24)
        relevant   = _filter_relevant(headlines, entity)

        # Si no hay titulares relevantes, intentar con todos (puede que la anomalía sea de otro tipo)
        context    = relevant if relevant else headlines[:5]

        explanation = _call_groq(entity.name, anomaly.metric, anomaly.z_score, context)
        if explanation:
            anomaly.context_explanation = explanation
            logger.info(f"[ContextAgent] Explicación generada para {entity.name} ({anomaly.metric})")
            return True

    except Exception as exc:
        logger.error(f"[ContextAgent] Error en explain_anomaly: {exc}", exc_info=True)

    return False


def run_context_analysis(db, hours: int = 2) -> dict:
    """
    Procesa todas las anomalías recientes sin explicación de contexto.
    Llamado desde la tarea Celery detect_anomalies después del commit.
    """
    from app.core.config import settings
    if not settings.GROQ_API_KEY:
        return {"status": "skipped", "reason": "no_groq_key"}

    from app.models.anomaly import Anomaly

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    anomalies = db.query(Anomaly).filter(
        Anomaly.detected_at         >= since,
        Anomaly.context_explanation == None,  # noqa: E711
    ).all()

    explained = 0
    for anomaly in anomalies:
        if explain_anomaly(db, anomaly):
            explained += 1

    if explained:
        db.commit()

    result = {"explained": explained, "total": len(anomalies)}
    logger.info(f"[ContextAgent] Análisis de contexto: {result}")
    return result
