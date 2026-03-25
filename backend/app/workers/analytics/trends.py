"""
Predicción de tendencias de menciones usando suavizado exponencial de Holt
(tendencia lineal amortiguada, sin estacionalidad).

Estrategia:
  - Recolecta los últimos 30 días de conteos diarios por entidad.
  - Si hay >= 7 días con datos, aplica Holt-Winters damped (statsmodels).
  - Fallback: regresión lineal OLS si statsmodels falla o la serie es muy corta.
  - Guarda pronóstico de 7 días en `trend_forecasts` (upsert por entidad+fecha).
"""
import logging
import warnings
from datetime import date, datetime, timedelta, timezone

import numpy as np

logger = logging.getLogger(__name__)

HISTORY_DAYS    = 30
MIN_NONZERO     = 7
FORECAST_HORIZON = 7


# ── Recolección de historial ──────────────────────────────────────

def _collect_history(db, entity_id) -> tuple[list[date], list[float]]:
    """Retorna (fechas, conteos) de los últimos HISTORY_DAYS días."""
    from sqlalchemy import func
    from app.models.mention import Mention

    now   = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    dates, counts = [], []
    for i in range(HISTORY_DAYS - 1, -1, -1):
        day_start = today - timedelta(days=i)
        day_end   = day_start + timedelta(days=1)
        cnt = db.query(func.count(Mention.id)).filter(
            Mention.entity_id    == entity_id,
            Mention.collected_at >= day_start,
            Mention.collected_at <  day_end,
        ).scalar() or 0
        dates.append(day_start.date())
        counts.append(float(cnt))

    return dates, counts


# ── Algoritmos de pronóstico ──────────────────────────────────────

def _holt_forecast(counts: list[float]) -> tuple[list[float], list[float], list[float]]:
    """
    Suavizado exponencial de Holt con tendencia amortiguada.
    Retorna (predicted, conf_low, conf_high) para FORECAST_HORIZON días.
    """
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = ExponentialSmoothing(
                counts,
                trend="add",
                damped_trend=True,
                initialization_method="estimated",
            ).fit(optimized=True)

        forecast  = model.forecast(FORECAST_HORIZON)
        residuals = np.array(counts) - model.fittedvalues
        rmse      = float(np.sqrt(np.mean(residuals ** 2)))
        margin    = 1.96 * max(rmse, 0.5)  # mínimo 0.5 para CI visible

        predicted   = [max(0.0, float(v)) for v in forecast]
        conf_low    = [max(0.0, p - margin) for p in predicted]
        conf_high   = [p + margin for p in predicted]
        return predicted, conf_low, conf_high, "holt_damped"

    except Exception as exc:
        logger.warning(f"[Trends] Holt falló ({exc}), usando regresión lineal")
        return _linear_forecast(counts)


def _linear_forecast(counts: list[float]) -> tuple[list[float], list[float], list[float], str]:
    """Regresión lineal OLS como fallback."""
    n = len(counts)
    x = np.arange(n, dtype=float)
    y = np.array(counts, dtype=float)

    x_mean, y_mean = x.mean(), y.mean()
    denom  = float(np.sum((x - x_mean) ** 2))
    slope  = float(np.sum((x - x_mean) * (y - y_mean)) / denom) if denom else 0.0
    intercept = float(y_mean - slope * x_mean)

    predicted = [max(0.0, intercept + slope * (n + i)) for i in range(FORECAST_HORIZON)]

    residuals = y - (intercept + slope * x)
    rmse      = float(np.sqrt(np.mean(residuals ** 2)))
    margin    = 1.96 * max(rmse, 0.5)

    conf_low  = [max(0.0, p - margin) for p in predicted]
    conf_high = [p + margin for p in predicted]
    return predicted, conf_low, conf_high, "linear_ols"


# ── Función principal por entidad ─────────────────────────────────

def forecast_entity(db, entity) -> dict:
    """
    Genera el pronóstico de 7 días para una entidad y lo persiste en BD.
    Devuelve dict con status: ok | skipped.
    """
    from app.models.trend import TrendForecast

    hist_dates, hist_counts = _collect_history(db, entity.id)

    non_zero = sum(1 for c in hist_counts if c > 0)
    if non_zero < MIN_NONZERO:
        return {
            "status": "skipped",
            "reason": "insufficient_data",
            "entity": entity.name,
            "non_zero_days": non_zero,
        }

    predicted, conf_low, conf_high, model_name = _holt_forecast(hist_counts)

    today   = datetime.now(timezone.utc).date()
    now_utc = datetime.now(timezone.utc)

    # Upsert: elimina pronósticos futuros existentes y reescribe
    db.query(TrendForecast).filter(
        TrendForecast.entity_id    == entity.id,
        TrendForecast.forecast_date >= today + timedelta(days=1),
    ).delete(synchronize_session=False)

    for i in range(FORECAST_HORIZON):
        fc_date = today + timedelta(days=i + 1)
        db.add(TrendForecast(
            entity_id       = entity.id,
            forecast_date   = fc_date,
            predicted_count = round(predicted[i], 2),
            confidence_low  = round(conf_low[i],  2),
            confidence_high = round(conf_high[i], 2),
            model_used      = model_name,
            generated_at    = now_utc,
        ))

    return {
        "status":  "ok",
        "entity":  entity.name,
        "model":   model_name,
        "horizon": FORECAST_HORIZON,
        "forecast": [
            {
                "date":      str(today + timedelta(days=i + 1)),
                "predicted": round(predicted[i], 1),
                "low":       round(conf_low[i],  1),
                "high":      round(conf_high[i], 1),
            }
            for i in range(FORECAST_HORIZON)
        ],
    }


# ── Ejecución global ──────────────────────────────────────────────

def run_trend_forecasting(db) -> dict:
    """Genera pronósticos para todas las entidades activas."""
    from app.models.entity import Entity

    entities = db.query(Entity).filter(Entity.active == True).all()
    results  = {"ok": 0, "skipped": 0, "errors": 0, "total": len(entities)}

    for entity in entities:
        try:
            r = forecast_entity(db, entity)
            if r.get("status") == "ok":
                results["ok"] += 1
            else:
                results["skipped"] += 1
        except Exception as exc:
            logger.error(f"[Trends] Error en {entity.name}: {exc}", exc_info=True)
            results["errors"] += 1

    db.commit()
    logger.info(f"[Trends] Pronósticos: {results}")
    return results
