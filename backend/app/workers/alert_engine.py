"""
Motor de evaluación de reglas de alerta.

Evaluadores implementados:
  - VOLUME_SPIKE       : menciones recientes vs promedio histórico (7 días)
  - NEGATIVE_THRESHOLD : % menciones negativas en la ventana
  - BOT_ACTIVITY       : cantidad de bots activos en la ventana
  - KEYWORD_CRITICAL   : menciones con keywords de peso 3
  - HATE_SPEECH        : menciones con is_hate_speech=True
  - CAMPAIGN_DETECTED  : textos similares de múltiples cuentas distintas

Cooldown: no se dispara la misma regla dos veces en menos de COOLDOWN_MINUTES.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from itertools import combinations
from typing import Optional

import redis as redis_lib
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import SessionLocal
from app.models.alert import Alert, AlertRule
from app.models.bot import AccountProfile, BotAnalysis
from app.models.entity import Entity, EntityType, Keyword
from app.models.mention import Mention
from app.models.user import User

logger = logging.getLogger(__name__)

COOLDOWN_MINUTES     = 30    # mínimo entre dos alertas iguales para la misma regla
MIN_MENTIONS_FOR_PCT = 10    # mínimo de menciones para evaluar porcentajes
CAMPAIGN_MIN_ACCOUNTS = 3   # mínimo de cuentas distintas para detectar campaña
CAMPAIGN_SIMILARITY   = 0.75 # similitud de texto para considerar mensajes coordinados


# ── Helpers ───────────────────────────────────────────────────

def _window_start(window_minutes: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=window_minutes)


def _in_cooldown(db: Session, rule: AlertRule) -> bool:
    """Verifica si la regla ya disparó una alerta recientemente."""
    cooldown_since = datetime.now(timezone.utc) - timedelta(minutes=COOLDOWN_MINUTES)
    recent = db.query(Alert.id).filter(
        Alert.rule_id     == rule.id,
        Alert.triggered_at >= cooldown_since,
    ).first()
    return recent is not None


def _historical_average(db: Session, entity_id, window_minutes: int) -> float:
    """
    Calcula el promedio histórico de menciones para la misma ventana
    de tiempo durante los últimos 7 días (excluye la ventana actual).
    """
    now       = datetime.now(timezone.utc)
    since_7d  = now - timedelta(days=7)
    samples   = []

    # Tomar 7 muestras (una por día a la misma hora)
    for days_ago in range(1, 8):
        sample_end   = now - timedelta(days=days_ago)
        sample_start = sample_end - timedelta(minutes=window_minutes)
        count = db.query(func.count(Mention.id)).filter(
            Mention.entity_id   == entity_id,
            Mention.collected_at >= sample_start,
            Mention.collected_at <  sample_end,
        ).scalar() or 0
        samples.append(count)

    return sum(samples) / len(samples) if samples else 0


# ── Evaluadores por tipo de regla ─────────────────────────────

def _check_volume_spike(db: Session, rule: AlertRule) -> Optional[str]:
    """
    Dispara si el volumen actual supera N veces el promedio histórico.
    rule.threshold = multiplicador (ej: 3 → 3x el promedio)
    """
    since   = _window_start(rule.window_minutes)
    current = db.query(func.count(Mention.id)).filter(
        Mention.entity_id   == rule.entity_id,
        Mention.collected_at >= since,
    ).scalar() or 0

    avg = _historical_average(db, rule.entity_id, rule.window_minutes)

    # Necesitamos al menos 3 menciones históricas promedio para comparar
    if avg < 3 and current < 10:
        return None

    if current >= max(avg * rule.threshold, 10):
        avg_str = f"{avg:.0f}" if avg >= 1 else "<1"
        return (
            f"{current} menciones en los últimos {rule.window_minutes} min "
            f"(promedio histórico: {avg_str}/ventana · "
            f"{rule.threshold}x superado)."
        )
    return None


def _check_negative_threshold(db: Session, rule: AlertRule) -> Optional[str]:
    """
    Dispara si el % de menciones negativas supera el umbral.
    rule.threshold = porcentaje (ej: 70 → 70%)
    """
    since = _window_start(rule.window_minutes)
    total = db.query(func.count(Mention.id)).filter(
        Mention.entity_id   == rule.entity_id,
        Mention.collected_at >= since,
        Mention.processed   == True,
    ).scalar() or 0

    if total < MIN_MENTIONS_FOR_PCT:
        return None

    negatives = db.query(func.count(Mention.id)).filter(
        Mention.entity_id     == rule.entity_id,
        Mention.collected_at  >= since,
        Mention.processed     == True,
        Mention.sentiment_label.in_(["negative", "very_negative"]),
    ).scalar() or 0

    pct = (negatives / total) * 100
    if pct >= rule.threshold:
        return (
            f"{pct:.1f}% de menciones son negativas "
            f"({negatives} de {total} en los últimos {rule.window_minutes} min · "
            f"umbral: {rule.threshold}%)."
        )
    return None


def _check_bot_activity(db: Session, rule: AlertRule) -> Optional[str]:
    """
    Dispara si se detectaron N o más bots activos en la ventana.
    rule.threshold = cantidad de bots
    """
    since = _window_start(rule.window_minutes)

    # Bots que publicaron menciones de esta entidad en la ventana
    bot_accounts = (
        db.query(func.count(func.distinct(Mention.author_ext_id)))
        .join(AccountProfile,
              (AccountProfile.platform_id    == Mention.platform_id) &
              (AccountProfile.external_user_id == Mention.author_ext_id))
        .join(BotAnalysis,
              BotAnalysis.account_profile_id == AccountProfile.id)
        .filter(
            Mention.entity_id    == rule.entity_id,
            Mention.collected_at >= since,
            BotAnalysis.classification == "bot",
        )
        .scalar() or 0
    )

    if bot_accounts >= rule.threshold:
        return (
            f"{bot_accounts} cuentas bot detectadas publicando sobre la entidad "
            f"en los últimos {rule.window_minutes} min "
            f"(umbral: {rule.threshold})."
        )
    return None


def _check_keyword_critical(db: Session, rule: AlertRule) -> Optional[str]:
    """
    Dispara si hay menciones de keywords con peso 3 (crítico).
    rule.threshold = cantidad mínima de menciones críticas
    """
    since = _window_start(rule.window_minutes)

    critical_kw_ids = [
        str(k.id)
        for k in db.query(Keyword).filter(
            Keyword.entity_id == rule.entity_id,
            Keyword.weight    == 3,
            Keyword.active    == True,
        ).all()
    ]

    if not critical_kw_ids:
        return None

    # Menciones que tienen al menos una keyword crítica
    from app.models.mention import mention_keywords
    count = (
        db.query(func.count(func.distinct(Mention.id)))
        .join(mention_keywords, mention_keywords.c.mention_id == Mention.id)
        .filter(
            Mention.entity_id    == rule.entity_id,
            Mention.collected_at >= since,
            mention_keywords.c.keyword_id.in_(critical_kw_ids),
        )
        .scalar() or 0
    )

    if count >= rule.threshold:
        # Obtener los keywords que aparecieron
        kw_names = [
            k.keyword
            for k in db.query(Keyword).filter(
                Keyword.id.in_(critical_kw_ids)
            ).limit(5).all()
        ]
        kw_list = ", ".join(f'"{k}"' for k in kw_names)
        return (
            f"{count} menciones con keywords críticas detectadas en "
            f"los últimos {rule.window_minutes} min: {kw_list}."
        )
    return None


def _check_hate_speech(db: Session, rule: AlertRule) -> Optional[str]:
    """
    Dispara si hay N o más menciones con discurso de odio en la ventana.
    rule.threshold = cantidad mínima
    """
    since = _window_start(rule.window_minutes)

    count = db.query(func.count(Mention.id)).filter(
        Mention.entity_id    == rule.entity_id,
        Mention.collected_at >= since,
        Mention.is_hate_speech == True,
    ).scalar() or 0

    if count >= rule.threshold:
        return (
            f"{count} publicaciones con discurso de odio detectadas "
            f"en los últimos {rule.window_minutes} min "
            f"(umbral: {rule.threshold})."
        )
    return None


def _check_campaign_detected(db: Session, rule: AlertRule) -> Optional[str]:
    """
    Detecta actividad coordinada: múltiples cuentas distintas publicando
    contenido similar en la misma ventana de tiempo.
    rule.threshold = cantidad mínima de cuentas coordinadas
    """
    since = _window_start(rule.window_minutes)

    mentions = db.query(Mention).filter(
        Mention.entity_id    == rule.entity_id,
        Mention.collected_at >= since,
        Mention.content_clean.isnot(None),
    ).limit(200).all()

    if len(mentions) < CAMPAIGN_MIN_ACCOUNTS:
        return None

    # Agrupar por autor
    by_author: dict[str, list[str]] = {}
    for m in mentions:
        author = m.author_username or m.author_ext_id or "unknown"
        by_author.setdefault(author, []).append(m.content_clean or "")

    if len(by_author) < CAMPAIGN_MIN_ACCOUNTS:
        return None

    # Tomar un texto representativo por autor (el más largo)
    representative = {
        author: max(texts, key=len)
        for author, texts in by_author.items()
    }

    # Buscar pares de autores con contenido muy similar
    authors     = list(representative.keys())
    sim_pairs   = 0
    sim_accounts = set()

    for a, b in combinations(authors[:50], 2):   # limitar a 50 para eficiencia
        ratio = SequenceMatcher(None,
                                representative[a][:300],
                                representative[b][:300]).ratio()
        if ratio >= CAMPAIGN_SIMILARITY:
            sim_pairs += 1
            sim_accounts.update([a, b])

    if len(sim_accounts) >= rule.threshold:
        return (
            f"Posible campaña coordinada detectada: "
            f"{len(sim_accounts)} cuentas publicando contenido similar "
            f"en los últimos {rule.window_minutes} min "
            f"({sim_pairs} pares de mensajes similares)."
        )
    return None


# ── Mapa de evaluadores ───────────────────────────────────────

EVALUATORS = {
    "volume_spike":       _check_volume_spike,
    "negative_threshold": _check_negative_threshold,
    "bot_activity":       _check_bot_activity,
    "keyword_critical":   _check_keyword_critical,
    "hate_speech":        _check_hate_speech,
    "campaign_detected":  _check_campaign_detected,
}


def evaluate_rule(db: Session, rule: AlertRule) -> Optional[Alert]:
    """
    Evalúa una regla. Si se cumple la condición, crea y retorna una Alert.
    Retorna None si no se dispara.
    """
    if _in_cooldown(db, rule):
        return None

    evaluator = EVALUATORS.get(rule.rule_type)
    if not evaluator:
        logger.warning(f"Evaluador no encontrado para tipo: {rule.rule_type}")
        return None

    try:
        message = evaluator(db, rule)
    except Exception as e:
        logger.error(f"Error evaluando regla {rule.id} ({rule.rule_type}): {e}", exc_info=True)
        return None

    if not message:
        return None

    alert = Alert(
        rule_id   = rule.id,
        entity_id = rule.entity_id,
        message   = message,
        severity  = rule.severity,
    )
    db.add(alert)
    db.flush()   # para obtener alert.id antes del commit
    return alert


# ── Tabla de canales por severidad ────────────────────────────
#   low      → solo dashboard (SSE)
#   medium   → Telegram + dashboard
#   high     → Telegram + WhatsApp + Email + dashboard
#   critical → Telegram + WhatsApp + Email + dashboard

_NOTIFY_TELEGRAM  = {"medium", "high", "critical"}
_NOTIFY_WHATSAPP  = {"high", "critical"}
_NOTIFY_EMAIL     = {"high", "critical"}


def _build_alert_data(alert: Alert, rule: AlertRule, entity_name: str) -> dict:
    return {
        "id":           str(alert.id),
        "rule_id":      str(rule.id),
        "rule_type":    rule.rule_type,
        "entity_id":    str(alert.entity_id),
        "entity_name":  entity_name,
        "severity":     alert.severity,
        "message":      alert.message,
        "triggered_at": alert.triggered_at.strftime("%d/%m/%Y %H:%M UTC")
                        if alert.triggered_at else
                        datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
    }


def _push_to_redis(r: redis_lib.Redis, user_id, alert_data: dict) -> None:
    """Publica la alerta en el canal SSE del usuario (lista Redis)."""
    key = f"alerts:{user_id}"
    r.lpush(key, json.dumps(alert_data))
    r.ltrim(key, 0, 49)          # máximo 50 alertas en cola por usuario
    r.expire(key, 3600)           # expira en 1 hora


def _dispatch_notifications(
    db: Session,
    r: redis_lib.Redis,
    alert: Alert,
    rule: AlertRule,
    entity_name: str,
) -> None:
    """
    Envía notificaciones a todos los usuarios activos (admin + analyst)
    según la severidad de la alerta. Siempre empuja al dashboard vía Redis.
    """
    from app.notifications.email    import send_email
    from app.notifications.telegram import send_telegram
    from app.notifications.whatsapp import send_whatsapp

    severity   = alert.severity
    alert_data = _build_alert_data(alert, rule, entity_name)

    # Usuarios que deben recibir notificaciones (admins y analistas activos)
    users: list[User] = (
        db.query(User)
        .filter(
            User.active == True,
            User.role.in_(["admin", "analyst"]),
        )
        .all()
    )

    for user in users:
        # Siempre push al dashboard SSE
        _push_to_redis(r, str(user.id), alert_data)

        # Telegram
        if severity in _NOTIFY_TELEGRAM and user.notify_telegram and user.telegram_chat_id:
            send_telegram(user.telegram_chat_id, alert_data)

        # WhatsApp
        if severity in _NOTIFY_WHATSAPP and user.notify_whatsapp \
                and user.whatsapp_phone and user.whatsapp_api_key:
            send_whatsapp(user.whatsapp_phone, user.whatsapp_api_key, alert_data)

        # Email
        if severity in _NOTIFY_EMAIL and user.notify_email and user.email:
            send_email(user.email, alert_data)


# ── Orquestador principal ──────────────────────────────────────

def run_alert_engine() -> dict:
    """
    Evalúa todas las reglas de alerta activas y despacha notificaciones.
    Retorna un resumen de la ejecución.
    """
    fired   = 0
    skipped = 0
    errors  = 0

    try:
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception as exc:
        logger.error(f"No se pudo conectar a Redis: {exc}")
        r = None

    db: Session = SessionLocal()
    try:
        rules: list[AlertRule] = (
            db.query(AlertRule)
            .filter(AlertRule.active == True)
            .all()
        )

        # Excluir reglas cuya entidad es un feed del Twitter Explorer
        feed_entity_ids = {
            row[0] for row in
            db.query(Entity.id)
            .join(EntityType, Entity.entity_type_id == EntityType.id)
            .filter(EntityType.name == "Monitor Twitter")
            .all()
        }
        rules = [r for r in rules if r.entity_id not in feed_entity_ids]

        logger.info(f"Motor de alertas: evaluando {len(rules)} reglas activas.")

        for rule in rules:
            try:
                alert = evaluate_rule(db, rule)
                if alert is None:
                    skipped += 1
                    continue

                # Obtener nombre de entidad para mensajes
                entity = db.query(Entity).filter(Entity.id == rule.entity_id).first()
                entity_name = entity.name if entity else str(rule.entity_id)

                if r is not None:
                    _dispatch_notifications(db, r, alert, rule, entity_name)
                else:
                    logger.warning(
                        f"Redis no disponible — alerta {alert.id} guardada pero "
                        "sin notificaciones en tiempo real."
                    )

                fired += 1
                logger.info(
                    f"Alerta disparada: regla={rule.name!r} "
                    f"entidad={entity_name!r} severidad={rule.severity}"
                )

            except Exception as exc:
                errors += 1
                logger.error(
                    f"Error procesando regla {rule.id} ({rule.rule_type}): {exc}",
                    exc_info=True,
                )

        db.commit()

    except Exception as exc:
        db.rollback()
        logger.error(f"Error fatal en motor de alertas: {exc}", exc_info=True)
        errors += 1
    finally:
        db.close()

    summary = {"fired": fired, "skipped": skipped, "errors": errors}
    logger.info(f"Motor de alertas completado: {summary}")
    return summary
