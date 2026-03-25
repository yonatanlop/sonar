"""
Módulo de Detección de Anomalías — v2

Algoritmo: Z-score sobre ventana de 7 días por entidad y métrica.

Métricas analizadas:
  volume       — número de menciones diarias
  negative_pct — porcentaje de menciones negativas diarias

Flujo:
  1. Para cada entidad activa, obtener conteos diarios D-7 a D-1 (baseline)
  2. Obtener el valor del día actual (D-0)
  3. Calcular z_score = (valor_actual - media) / desv_estandar
  4. Si z_score >= ZSCORE_THRESHOLD → guardar Anomaly + crear Alert
  5. Despachar notificación via Redis (SSE) si la severidad lo amerita

El threshold por defecto es 2.5:
  z = 2.5 → el valor actual es 2.5 desviaciones estándar sobre la media.
  Con datos normales, eso ocurre <1% del tiempo, por lo que indica un evento real.
"""
import logging
import math
import statistics
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertRule
from app.models.anomaly import Anomaly
from app.models.entity import Entity
from app.models.mention import Mention

logger = logging.getLogger(__name__)

ZSCORE_THRESHOLD  = 2.5   # umbral de detección
MIN_DAILY_AVERAGE = 3.0   # mínimo promedio diario para analizar (evitar ruido con pocas menciones)
COOLDOWN_HOURS    = 6     # horas mínimas entre dos anomalías del mismo tipo para la misma entidad


# ── Helpers ────────────────────────────────────────────────────────────────

def _daily_volume(db: Session, entity_id, target_date: date) -> int:
    """Menciones de la entidad en un día calendario."""
    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    day_end   = day_start + timedelta(days=1)
    return db.query(func.count(Mention.id)).filter(
        Mention.entity_id    == entity_id,
        Mention.collected_at >= day_start,
        Mention.collected_at <  day_end,
    ).scalar() or 0


def _daily_negative_pct(db: Session, entity_id, target_date: date) -> float | None:
    """Porcentaje de menciones negativas de la entidad en un día."""
    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    day_end   = day_start + timedelta(days=1)

    total = db.query(func.count(Mention.id)).filter(
        Mention.entity_id    == entity_id,
        Mention.collected_at >= day_start,
        Mention.collected_at <  day_end,
        Mention.processed    == True,
    ).scalar() or 0

    if total < 5:   # insuficiente para calcular porcentaje
        return None

    negatives = db.query(func.count(Mention.id)).filter(
        Mention.entity_id     == entity_id,
        Mention.collected_at  >= day_start,
        Mention.collected_at  <  day_end,
        Mention.processed     == True,
        Mention.sentiment_label.in_(["negative", "very_negative"]),
    ).scalar() or 0

    return (negatives / total) * 100.0


def _in_cooldown(db: Session, entity_id, metric: str) -> bool:
    """Evita disparar la misma anomalía varias veces en el período de cooldown."""
    since = datetime.now(timezone.utc) - timedelta(hours=COOLDOWN_HOURS)
    return db.query(Anomaly.id).filter(
        Anomaly.entity_id  == entity_id,
        Anomaly.metric     == metric,
        Anomaly.detected_at >= since,
    ).first() is not None


def _z_score(value: float, baseline: list[float]) -> tuple[float, float, float]:
    """
    Calcula z_score, media y desviación estándar.
    Retorna (z_score, mean, std_dev).
    """
    if len(baseline) < 3:
        return 0.0, 0.0, 0.0

    mean = statistics.mean(baseline)
    try:
        std = statistics.stdev(baseline)
    except statistics.StatisticsError:
        std = 0.0

    if std < 0.01:   # varianza prácticamente cero
        return 0.0, mean, std

    z = (value - mean) / std
    return z, mean, std


def _get_or_create_system_rule(db: Session, entity_id) -> AlertRule:
    """
    Obtiene o crea la regla de sistema para anomalías de esta entidad.
    Estas reglas tienen created_by=NULL y no son visibles en la UI de reglas de usuario.
    """
    rule = db.query(AlertRule).filter(
        AlertRule.entity_id == entity_id,
        AlertRule.rule_type == "anomaly_detected",
        AlertRule.active    == True,
    ).first()

    if not rule:
        rule = AlertRule(
            entity_id      = entity_id,
            name           = "Anomalía detectada automáticamente",
            rule_type      = "anomaly_detected",
            threshold      = 1,
            window_minutes = 1440,
            severity       = "high",
            active         = True,
            created_by     = None,   # regla de sistema
        )
        db.add(rule)
        db.flush()

    return rule


def _severity_for_zscore(z: float) -> str:
    if z >= 4.0:
        return "critical"
    if z >= 3.0:
        return "high"
    return "medium"


def _create_alert_for_anomaly(
    db: Session,
    entity: Entity,
    anomaly: Anomaly,
) -> Alert | None:
    """Crea una alerta vinculada a la anomalía detectada."""
    rule = _get_or_create_system_rule(db, entity.id)

    metric_label = "volumen de menciones" if anomaly.metric == "volume" else "menciones negativas"
    pct_suffix   = "%" if anomaly.metric == "negative_pct" else ""
    severity     = _severity_for_zscore(anomaly.z_score)

    message = (
        f"Anomalía detectada en {entity.name}: "
        f"{metric_label} inusualmente alto. "
        f"Valor actual: {anomaly.value:.1f}{pct_suffix} "
        f"(media histórica: {anomaly.baseline:.1f}{pct_suffix}, "
        f"z-score: {anomaly.z_score:.2f})."
    )

    alert = Alert(
        rule_id      = rule.id,
        entity_id    = entity.id,
        message      = message,
        severity     = severity,
        anomaly_id   = anomaly.id,   # v2: vínculo directo para contexto IA
    )
    db.add(alert)
    db.flush()
    return alert


# ── Detección por entidad ──────────────────────────────────────────────────

def detect_for_entity(db: Session, entity: Entity) -> list[Anomaly]:
    """
    Analiza una entidad y retorna la lista de anomalías nuevas detectadas.
    Las anomalías ya están añadidas a la sesión (pendientes de commit).
    """
    today     = date.today()
    detected  = []

    # ── Métrica 1: volumen ───────────────────────────────────────
    if not _in_cooldown(db, entity.id, "volume"):
        baseline_vol = [_daily_volume(db, entity.id, today - timedelta(days=d)) for d in range(1, 8)]
        current_vol  = _daily_volume(db, entity.id, today)
        mean_vol     = statistics.mean(baseline_vol) if baseline_vol else 0

        if mean_vol >= MIN_DAILY_AVERAGE:
            z, mean, std = _z_score(float(current_vol), [float(v) for v in baseline_vol])
            if z >= ZSCORE_THRESHOLD:
                anomaly = Anomaly(
                    entity_id  = entity.id,
                    metric     = "volume",
                    z_score    = round(z, 3),
                    value      = float(current_vol),
                    baseline   = round(mean, 2),
                    std_dev    = round(std, 2),
                )
                db.add(anomaly)
                db.flush()
                _create_alert_for_anomaly(db, entity, anomaly)
                detected.append(anomaly)
                logger.info(
                    f"[Anomaly] {entity.name} — volumen z={z:.2f} "
                    f"(actual={current_vol}, media={mean:.1f})"
                )

    # ── Métrica 2: porcentaje negativo ───────────────────────────
    if not _in_cooldown(db, entity.id, "negative_pct"):
        baseline_pct = [_daily_negative_pct(db, entity.id, today - timedelta(days=d)) for d in range(1, 8)]
        baseline_pct = [v for v in baseline_pct if v is not None]
        current_pct  = _daily_negative_pct(db, entity.id, today)

        if len(baseline_pct) >= 3 and current_pct is not None:
            z, mean, std = _z_score(current_pct, baseline_pct)
            if z >= ZSCORE_THRESHOLD:
                anomaly = Anomaly(
                    entity_id  = entity.id,
                    metric     = "negative_pct",
                    z_score    = round(z, 3),
                    value      = round(current_pct, 2),
                    baseline   = round(mean, 2),
                    std_dev    = round(std, 2),
                )
                db.add(anomaly)
                db.flush()
                _create_alert_for_anomaly(db, entity, anomaly)
                detected.append(anomaly)
                logger.info(
                    f"[Anomaly] {entity.name} — negativo z={z:.2f} "
                    f"(actual={current_pct:.1f}%, media={mean:.1f}%)"
                )

    return detected


# ── Orquestador ────────────────────────────────────────────────────────────

def run_anomaly_detection(db: Session) -> dict:
    """
    Recorre todas las entidades activas y detecta anomalías.
    Llamado por la tarea Celery cada 30 minutos.
    """
    entities = db.query(Entity).filter(Entity.active == True).all()
    total_anomalies = 0
    errors          = 0

    logger.info(f"[Anomaly] Iniciando detección sobre {len(entities)} entidades.")

    for entity in entities:
        try:
            found = detect_for_entity(db, entity)
            total_anomalies += len(found)
        except Exception as exc:
            logger.error(f"[Anomaly] Error en entidad {entity.name}: {exc}", exc_info=True)
            errors += 1

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"[Anomaly] Error en commit: {exc}", exc_info=True)
        errors += 1

    summary = {"anomalies_detected": total_anomalies, "entities_checked": len(entities), "errors": errors}
    logger.info(f"[Anomaly] Completado: {summary}")

    # Despachar alertas vía Redis SSE para las anomalías guardadas
    if total_anomalies > 0:
        _dispatch_anomaly_alerts(db)

    return summary


def _dispatch_anomaly_alerts(db: Session) -> None:
    """
    Empuja las alertas de anomalía recientes al canal SSE de Redis.
    Reutiliza la infraestructura del motor de alertas.
    """
    try:
        from app.workers.alert_engine import _build_alert_data, _push_to_redis
        from app.models.user import User
        import redis as redis_lib
        from app.core.config import settings

        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

        # Alertas de anomalía creadas en los últimos 2 minutos
        since = datetime.now(timezone.utc) - timedelta(minutes=2)
        recent_alerts = db.query(Alert).join(AlertRule).filter(
            AlertRule.rule_type == "anomaly_detected",
            Alert.triggered_at  >= since,
        ).all()

        if not recent_alerts:
            return

        users = db.query(User).filter(User.active == True, User.role.in_(["admin", "analyst"])).all()

        for alert in recent_alerts:
            rule       = db.query(AlertRule).filter(AlertRule.id == alert.rule_id).first()
            entity     = db.query(Entity).filter(Entity.id == alert.entity_id).first()
            entity_name = entity.name if entity else str(alert.entity_id)
            if rule:
                alert_data = _build_alert_data(alert, rule, entity_name)
                for user in users:
                    _push_to_redis(r, str(user.id), alert_data)

    except Exception as exc:
        logger.warning(f"[Anomaly] No se pudieron despachar alertas SSE: {exc}")
