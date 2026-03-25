"""
Módulo de Resumen Diario con LLM — v2

Usa Groq API (tier gratuito) con Llama-3.1-8b-instant para generar
un resumen ejecutivo de las menciones del día por entidad.

Tier gratuito de Groq (2025):
  - 14,400 tokens / minuto
  - Sin límite diario en requests
  - Modelo recomendado: llama-3.1-8b-instant (rápido, preciso, multilingüe)

Flujo:
  1. Obtener menciones de las últimas 24h para la entidad
  2. Seleccionar muestra representativa (máx 40 menciones)
  3. Construir prompt estructurado en español
  4. Llamar a Groq API
  5. Guardar en tabla daily_summaries (upsert por entity_id + fecha)
  6. Retornar el texto generado

Si GROQ_API_KEY no está configurado, la tarea se saltea sin error.
"""
import logging
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entity import Entity
from app.models.mention import Mention
from app.models.summary import DailySummary

logger = logging.getLogger(__name__)

MAX_MENTIONS_IN_PROMPT = 40    # máx menciones a incluir en el prompt
MAX_CHARS_PER_MENTION  = 280   # recortar menciones largas (tipo tweet)
MAX_PROMPT_CHARS       = 8_000 # límite conservador para el contexto


# ── Construcción del prompt ────────────────────────────────────────────────

def _build_prompt(entity_name: str, mentions: list[Mention]) -> str:
    """Construye el prompt para Groq con las menciones del día."""

    # Seleccionar una muestra balanceada por sentimiento
    by_sentiment: dict[str, list[Mention]] = {}
    for m in mentions:
        label = m.sentiment_label or "neutral"
        by_sentiment.setdefault(label, []).append(m)

    # Tomar proporcional de cada grupo, hasta MAX_MENTIONS_IN_PROMPT
    sampled: list[Mention] = []
    per_group = max(1, MAX_MENTIONS_IN_PROMPT // max(len(by_sentiment), 1))
    for group_mentions in by_sentiment.values():
        sampled.extend(random.sample(group_mentions, min(per_group, len(group_mentions))))

    if len(sampled) > MAX_MENTIONS_IN_PROMPT:
        sampled = random.sample(sampled, MAX_MENTIONS_IN_PROMPT)

    # Formatear las menciones
    lines = []
    total_chars = 0
    for i, m in enumerate(sampled, 1):
        text = (m.content_clean or m.content or "").strip()
        if len(text) > MAX_CHARS_PER_MENTION:
            text = text[:MAX_CHARS_PER_MENTION] + "…"
        platform = m.platform.code if m.platform else "?"
        sentiment = m.sentiment_label or "?"
        line = f"{i}. [{platform}|{sentiment}] {text}"
        total_chars += len(line)
        if total_chars > MAX_PROMPT_CHARS:
            break
        lines.append(line)

    mentions_block = "\n".join(lines)
    today_str = date.today().strftime("%d de %B de %Y")

    return f"""Eres un analista de reputación digital experto en monitoreo de redes sociales para América Latina.

Analiza las siguientes {len(sampled)} menciones sobre "{entity_name}" publicadas el {today_str} y genera un resumen ejecutivo conciso en español.

MENCIONES:
{mentions_block}

Responde ÚNICAMENTE con este formato, sin texto adicional antes ni después:

**Temas principales:**
• [Tema 1 — descripción breve en máx 15 palabras]
• [Tema 2 — descripción breve en máx 15 palabras]
• [Tema 3 — descripción breve en máx 15 palabras]

**Tono general:** [positivo / negativo / mixto / neutral] — [1 frase explicando el por qué]

**Punto de atención:** [Si hay algo crítico, inusual o urgente, mencionarlo en 1 frase. Si todo es normal, escribe exactamente: Sin alertas críticas.]"""


# ── Cliente Groq ───────────────────────────────────────────────────────────

def _call_groq(prompt: str) -> str:
    """
    Llama a Groq API y retorna el texto generado.
    Lanza excepción si falla.
    """
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("Paquete 'groq' no instalado. Ejecuta: pip install groq")

    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY no configurada en .env")

    client = Groq(api_key=settings.GROQ_API_KEY)
    response = client.chat.completions.create(
        model=settings.SUMMARY_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un analista de reputación. "
                    "Respondes siempre en español. "
                    "Eres conciso y preciso. "
                    "Nunca inventas información que no esté en las menciones."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,      # bajo para respuestas consistentes
        max_tokens=400,        # el formato pedido cabe en ~300 tokens
    )
    return response.choices[0].message.content.strip()


# ── Generación por entidad ─────────────────────────────────────────────────

def summarize_entity(db: Session, entity: Entity) -> DailySummary | None:
    """
    Genera y guarda el resumen del día para una entidad.
    Retorna el objeto DailySummary creado, o None si se saltea.
    """
    today = date.today()

    # ── Verificar si ya existe resumen para hoy ──────────────────
    existing = db.query(DailySummary).filter(
        DailySummary.entity_id   == entity.id,
        DailySummary.summary_date == today,
    ).first()
    if existing:
        logger.info(f"[Summary] {entity.name} — resumen de hoy ya existe, saltando.")
        return existing

    # ── Obtener menciones de las últimas 24h ─────────────────────
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    mentions = (
        db.query(Mention)
        .filter(
            Mention.entity_id    == entity.id,
            Mention.collected_at >= since,
            Mention.is_relevant  == True,
        )
        .order_by(Mention.urgency_score.desc())   # priorizar las más urgentes
        .limit(200)
        .all()
    )

    if len(mentions) < 3:
        logger.info(f"[Summary] {entity.name} — menos de 3 menciones hoy, saltando.")
        return None

    # ── Construir prompt y llamar a Groq ─────────────────────────
    try:
        prompt       = _build_prompt(entity.name, mentions)
        summary_text = _call_groq(prompt)
    except RuntimeError as exc:
        logger.warning(f"[Summary] {entity.name} — {exc}")
        return None
    except Exception as exc:
        logger.error(f"[Summary] {entity.name} — Error en Groq API: {exc}", exc_info=True)
        return None

    # ── Guardar en BD ─────────────────────────────────────────────
    summary = DailySummary(
        entity_id     = entity.id,
        summary_date  = today,
        summary_text  = summary_text,
        model_used    = settings.SUMMARY_MODEL,
        mention_count = len(mentions),
    )
    db.add(summary)
    db.flush()

    logger.info(
        f"[Summary] {entity.name} — resumen generado "
        f"({len(mentions)} menciones · modelo: {settings.SUMMARY_MODEL})"
    )
    return summary


# ── Orquestador ────────────────────────────────────────────────────────────

def run_daily_summaries(db: Session) -> dict:
    """
    Genera resúmenes para todas las entidades activas.
    Llamado por la tarea Celery a las 23:50 cada día.
    """
    if not settings.GROQ_API_KEY:
        logger.warning("[Summary] GROQ_API_KEY no configurada — tarea saltada.")
        return {"status": "skipped", "reason": "GROQ_API_KEY not set"}

    entities = db.query(Entity).filter(Entity.active == True).all()
    generated = 0
    skipped   = 0
    errors    = 0

    logger.info(f"[Summary] Iniciando generación para {len(entities)} entidades.")

    for entity in entities:
        try:
            result = summarize_entity(db, entity)
            if result:
                generated += 1
            else:
                skipped += 1
        except Exception as exc:
            logger.error(f"[Summary] Error en entidad {entity.name}: {exc}", exc_info=True)
            errors += 1

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"[Summary] Error en commit: {exc}", exc_info=True)
        errors += 1

    summary = {
        "status":    "ok",
        "generated": generated,
        "skipped":   skipped,
        "errors":    errors,
        "model":     settings.SUMMARY_MODEL,
    }
    logger.info(f"[Summary] Completado: {summary}")
    return summary
