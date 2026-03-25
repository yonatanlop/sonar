"""
Clasificador de Bots con ML — v2

Usa un GradientBoostingClassifier entrenado con datos sintéticos basados
en patrones reales de cuentas bot (Botometer research, Twitter bot studies).

Features del modelo (8 variables):
  ff_ratio          — followers / max(following, 1)  [bots: extremo alto o bajo]
  posts_per_day     — post_count / max(account_age_days, 1)  [bots: muy alto]
  has_photo         — 1 si tiene foto de perfil, 0 si no  [bots: 0]
  has_bio           — 1 si tiene bio, 0 si no  [bots: 0]
  is_verified       — 1 si cuenta verificada  [bots: siempre 0]
  digit_ratio       — proporción de dígitos en username  [bots: alto]
  username_length   — longitud del username  [bots: muy corto o muy largo]
  account_age_days  — días desde creación  [bots: reciente]

Flujo:
  1. Cargar modelo desde /app/storage/models/bot_model.pkl
  2. Si no existe → usar reglas heurísticas como fallback
  3. Extraer features de AccountProfile
  4. Predecir probabilidad de ser bot (0.0 – 1.0)
  5. Crear/actualizar BotAnalysis con clasificación y indicadores
  6. Guardar bot_probability en AccountProfile

Para entrenar y generar el modelo pkl:
  docker compose exec backend python scripts/train_bot_model.py
"""
import logging
import math
import os
import pickle
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bot import AccountProfile, BotAnalysis

logger = logging.getLogger(__name__)

MODEL_PATH = "/app/storage/models/bot_model.pkl"
FEATURE_ORDER = [
    "ff_ratio", "posts_per_day", "has_photo",
    "has_bio", "is_verified", "digit_ratio",
    "username_length", "account_age_days",
]


# ── Extracción de features ─────────────────────────────────────────────────

def _account_age_days(account_created: Optional[date]) -> float:
    if not account_created:
        return 180.0   # valor medio si se desconoce
    delta = date.today() - account_created
    return max(float(delta.days), 1.0)


def extract_features(profile: AccountProfile) -> dict:
    """Extrae las 8 features del perfil para el clasificador."""
    followers = float(profile.followers_count or 0)
    following = float(profile.following_count or 1)
    posts     = float(profile.post_count or 0)
    age_days  = _account_age_days(profile.account_created)
    username  = profile.username or ""

    # Ratio followers/following (bots tienden a extremos)
    ff_ratio = followers / max(following, 1.0)
    # Saturar en 500 para evitar outliers
    ff_ratio = min(ff_ratio, 500.0)

    # Posts por día (bots publican muy frecuente)
    posts_per_day = posts / age_days
    # Saturar en 200
    posts_per_day = min(posts_per_day, 200.0)

    # Proporción de dígitos en username
    digits = sum(1 for c in username if c.isdigit())
    digit_ratio = digits / max(len(username), 1)

    return {
        "ff_ratio":         ff_ratio,
        "posts_per_day":    posts_per_day,
        "has_photo":        1.0 if profile.has_profile_photo else 0.0,
        "has_bio":          1.0 if (profile.bio and len(profile.bio.strip()) > 5) else 0.0,
        "is_verified":      1.0 if profile.verified else 0.0,
        "digit_ratio":      digit_ratio,
        "username_length":  float(min(len(username), 50)),
        "account_age_days": min(age_days, 3650.0),   # cap 10 años
    }


def features_to_array(features: dict) -> list:
    return [features[k] for k in FEATURE_ORDER]


# ── Modelo / Fallback heurístico ───────────────────────────────────────────

def _load_model():
    """Carga el modelo pkl. Retorna None si no existe."""
    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, "rb") as f:
                return pickle.load(f)
        except Exception as exc:
            logger.warning(f"[BotML] No se pudo cargar modelo: {exc}")
    return None


def _heuristic_score(features: dict) -> float:
    """
    Fallback heurístico cuando el modelo pkl no está disponible.
    Devuelve probabilidad bot 0.0–1.0 basada en reglas ponderadas.
    """
    score = 0.0

    # Sin foto → +0.25
    if features["has_photo"] == 0:
        score += 0.25

    # Sin bio → +0.20
    if features["has_bio"] == 0:
        score += 0.20

    # Muchos dígitos en username → hasta +0.20
    score += features["digit_ratio"] * 0.20

    # Cuenta muy nueva (< 30 días) → +0.15
    if features["account_age_days"] < 30:
        score += 0.15

    # Posts muy frecuentes (> 50/día) → +0.20
    if features["posts_per_day"] > 50:
        score += 0.20
    elif features["posts_per_day"] > 20:
        score += 0.10

    # Ratio followers/following muy bajo (< 0.1) → +0.15
    if features["ff_ratio"] < 0.1:
        score += 0.15

    # Verificado → -0.30 (muy improbable que sea bot)
    if features["is_verified"] == 1:
        score -= 0.30

    return max(0.0, min(score, 1.0))


_MODEL_CACHE = None
_MODEL_LOADED = False


def predict_bot_probability(profile: AccountProfile) -> tuple[float, dict]:
    """
    Predice la probabilidad de bot para un perfil.
    Retorna (probability, features_dict).
    """
    global _MODEL_CACHE, _MODEL_LOADED

    features = extract_features(profile)

    if not _MODEL_LOADED:
        _MODEL_CACHE = _load_model()
        _MODEL_LOADED = True

    if _MODEL_CACHE is not None:
        try:
            X = [features_to_array(features)]
            prob = float(_MODEL_CACHE.predict_proba(X)[0][1])
            return prob, features
        except Exception as exc:
            logger.warning(f"[BotML] Error en predicción ML: {exc}, usando heurística")

    return _heuristic_score(features), features


# ── Clasificación y persistencia ───────────────────────────────────────────

def _classify(probability: float) -> str:
    threshold = settings.BOT_THRESHOLD
    if probability >= threshold:
        return "bot"
    if probability >= threshold * 0.7:
        return "suspicious"
    if probability < 0.15:
        return "real"
    return "anonymous"


def analyze_account(db: Session, profile: AccountProfile) -> BotAnalysis:
    """
    Clasifica una cuenta y crea/actualiza su BotAnalysis.
    """
    probability, features = predict_bot_probability(profile)
    classification = _classify(probability)

    analysis = BotAnalysis(
        account_profile_id = profile.id,
        bot_score          = Decimal(str(round(probability, 3))),
        classification     = classification,
        indicators         = {k: round(v, 4) for k, v in features.items()},
        analyzed_by        = "ml_v2" if _MODEL_CACHE else "heuristic_v2",
    )
    db.add(analysis)

    # Actualizar bot_probability en el perfil
    profile.bot_probability  = round(probability, 4)
    profile.last_analyzed_at = datetime.now(timezone.utc)

    return analysis


# ── Orquestador ────────────────────────────────────────────────────────────

def run_bot_classification(db: Session, hours_since_last: int = 24) -> dict:
    """
    Clasifica cuentas que no han sido analizadas en las últimas N horas.
    Llamado por la tarea Celery.
    """
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_since_last)

    profiles = (
        db.query(AccountProfile)
        .filter(
            (AccountProfile.last_analyzed_at.is_(None)) |
            (AccountProfile.last_analyzed_at < cutoff)
        )
        .limit(500)   # procesar máx 500 por ciclo
        .all()
    )

    if not profiles:
        return {"status": "ok", "analyzed": 0, "bots": 0, "suspicious": 0}

    analyzed   = 0
    bots       = 0
    suspicious = 0
    errors     = 0

    for profile in profiles:
        try:
            analysis = analyze_account(db, profile)
            analyzed += 1
            if analysis.classification == "bot":
                bots += 1
            elif analysis.classification == "suspicious":
                suspicious += 1
        except Exception as exc:
            logger.error(f"[BotML] Error en perfil {profile.username}: {exc}")
            errors += 1

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"[BotML] Error en commit: {exc}", exc_info=True)

    summary = {
        "status":    "ok",
        "analyzed":  analyzed,
        "bots":      bots,
        "suspicious": suspicious,
        "errors":    errors,
        "model":     "ml_v2" if _MODEL_CACHE else "heuristic_v2",
    }
    logger.info(f"[BotML] Completado: {summary}")
    return summary
