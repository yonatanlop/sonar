"""
Clasificador de Bots — v3 (heurística calibrada; el modelo ML es opcional)

Estado real (auditado 2026-09-25): el modelo /app/storage/models/bot_model.pkl NO existe en producción,
así que TODA la clasificación usa la heurística. Además el script de entrenamiento usa datos sintéticos.
No hay hoy un modelo entrenado con bots reales; la calibración con etiquetas reales (Drive del cliente:
"Semáforo de inautenticidad" / "Ataque coordinado") es la segunda etapa.

Features (8 variables, las mismas que espera un modelo pkl si existe):
  ff_ratio, posts_per_day, has_photo, has_bio, is_verified, digit_ratio, username_length,
  account_age_days.

Cambios v3 respecto a v2:
  • Solo se califican cuentas con datos básicos (seguidores y fecha de creación). YouTube/RSS/Facebook
    no los tienen: antes recibían valores por defecto (180 días, sin foto, sin bio) y salían
    "sospechosas" por FALTA DE DATOS (5.708 de 5.738 cuentas de YouTube).
  • La heurística ya no usa las señales rotas: `is_verified` (Twitter retiró la verificación clásica;
    quedaba 'blue' = cuenta de pago) y `has_photo=False` (la foto llegaba vacía por un bug del
    scraper). Solo una foto propia CONFIRMADA (True) resta puntaje. El puntaje se normaliza sobre las
    señales fiables (máx. 0,90) para conservar la escala 0-1.
  • Selección por prioridad: 1) autores de menciones de entidades monitoreadas, 2) cuentas nunca
    calificadas, 3) recalificar las más antiguas. Antes no había ORDER BY y las cuentas activas
    quedaban fuera (upsert_account_profile reseteaba last_analyzed_at).
  • Un solo BotAnalysis por cuenta, actualizado en sitio (antes se insertaba una fila por corrida:
    hasta 35 por cuenta).

Para entrenar un modelo pkl (opcional):
  docker compose exec backend python scripts/train_bot_model.py
"""
import logging
import os
import pickle
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.explorer import explorer_entity_ids_subq
from app.models.bot import AccountProfile, BotAnalysis
from app.models.mention import Mention

logger = logging.getLogger(__name__)

MODEL_PATH = "/app/storage/models/bot_model.pkl"
FEATURE_ORDER = [
    "ff_ratio", "posts_per_day", "has_photo",
    "has_bio", "is_verified", "digit_ratio",
    "username_length", "account_age_days",
]

HEURISTIC_VERSION = "heuristic_v3"
REANALYZE_AFTER_DAYS = 7       # recalificar una cuenta ya calificada cada N días
DEFAULT_BATCH = 1000           # cuentas por corrida (la tarea corre cada hora)
MONITORED_WINDOW_DAYS = 30     # "autor de conversación monitoreada" = publicó en los últimos N días
_HEURISTIC_MAX = 0.90          # suma de las señales fiables (bio .20 + dígitos .20 + nueva .15 + posts .20 + ratio .15)


# ── Datos mínimos ──────────────────────────────────────────────────────────

def has_enough_data(profile: AccountProfile) -> bool:
    """Una cuenta se califica solo si conocemos seguidores y fecha de creación."""
    return profile.followers_count is not None and profile.account_created is not None


# ── Extracción de features ─────────────────────────────────────────────────

def _account_age_days(account_created: Optional[date]) -> float:
    if not account_created:
        return 180.0   # valor medio si se desconoce (no ocurre: has_enough_data lo exige)
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
    ff_ratio = min(ff_ratio, 500.0)          # saturar outliers

    # Posts por día (bots publican muy frecuente)
    posts_per_day = min(posts / age_days, 200.0)

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


# ── Modelo / heurística ────────────────────────────────────────────────────

def _load_model():
    """Carga el modelo pkl. Retorna None si no existe (caso actual en producción)."""
    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, "rb") as f:
                return pickle.load(f)
        except Exception as exc:
            logger.warning(f"[BotML] No se pudo cargar modelo: {exc}")
    return None


def _heuristic_score(features: dict) -> float:
    """
    Probabilidad de bot 0.0–1.0 con reglas ponderadas sobre señales FIABLES.

    No se usan `is_verified` (dato obsoleto: 'blue' es una suscripción) ni `has_photo=False`
    (el scraper no recuperaba la foto). Solo una foto propia confirmada resta puntaje.
    """
    score = 0.0

    # Sin bio → +0.20
    if features["has_bio"] == 0:
        score += 0.20

    # Muchos dígitos en username → hasta +0.20
    score += features["digit_ratio"] * 0.20

    # Cuenta muy nueva (< 30 días) → +0.15
    if features["account_age_days"] < 30:
        score += 0.15

    # Posts muy frecuentes (> 50/día) → +0.20 ; (> 20/día) → +0.10
    if features["posts_per_day"] > 50:
        score += 0.20
    elif features["posts_per_day"] > 20:
        score += 0.10

    # Ratio followers/following muy bajo (< 0.1) → +0.15
    if features["ff_ratio"] < 0.1:
        score += 0.15

    score = score / _HEURISTIC_MAX          # renormalizar a escala 0-1 sobre las señales fiables

    # Foto propia confirmada → -0.10
    if features["has_photo"] == 1:
        score -= 0.10

    return max(0.0, min(score, 1.0))


_MODEL_CACHE = None
_MODEL_LOADED = False


def predict_bot_probability(profile: AccountProfile) -> tuple[float, dict]:
    """Predice la probabilidad de bot para un perfil. Retorna (probability, features_dict)."""
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


def analyze_account(db: Session, profile: AccountProfile,
                    existing: Optional[BotAnalysis] = None) -> BotAnalysis:
    """
    Clasifica una cuenta y crea/actualiza su ÚNICO BotAnalysis (se actualiza en sitio).
    """
    probability, features = predict_bot_probability(profile)
    classification = _classify(probability)
    engine = "ml_v2" if _MODEL_CACHE else HEURISTIC_VERSION
    now = datetime.now(timezone.utc)

    if existing is not None:
        analysis = existing
        analysis.bot_score      = Decimal(str(round(probability, 3)))
        analysis.classification = classification
        analysis.indicators     = {k: round(v, 4) for k, v in features.items()}
        analysis.analyzed_by    = engine
        analysis.analyzed_at    = now
    else:
        analysis = BotAnalysis(
            account_profile_id = profile.id,
            bot_score          = Decimal(str(round(probability, 3))),
            classification     = classification,
            indicators         = {k: round(v, 4) for k, v in features.items()},
            analyzed_by        = engine,
        )
        db.add(analysis)

    profile.bot_probability  = round(probability, 4)
    profile.last_analyzed_at = now
    return analysis


# ── Selección por prioridad ────────────────────────────────────────────────

def monitored_author_ids(db: Session, days: int = MONITORED_WINDOW_DAYS) -> list:
    """IDs de perfiles que publicaron menciones relevantes de entidades parametrizadas (sin Explorer)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(AccountProfile.id)
        .join(Mention, and_(Mention.platform_id == AccountProfile.platform_id,
                            Mention.author_ext_id == AccountProfile.external_user_id))
        .filter(
            Mention.is_relevant == True,  # noqa: E712
            Mention.collected_at >= since,
            ~Mention.entity_id.in_(explorer_entity_ids_subq()),
        )
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


def select_profiles_to_analyze(db: Session, limit: int, reanalyze_after_days: int = REANALYZE_AFTER_DAYS):
    """
    Devuelve (perfiles, desglose_por_nivel) en este orden de prioridad:
      1) autores de menciones monitoreadas que necesitan (re)cálculo,
      2) cuentas que nunca han tenido puntaje,
      3) las ya calificadas hace más de `reanalyze_after_days`, las más antiguas primero.
    Solo cuentas con datos básicos (seguidores + fecha de creación).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=reanalyze_after_days)
    data_ok = and_(AccountProfile.followers_count.isnot(None), AccountProfile.account_created.isnot(None))
    needs = or_(
        AccountProfile.bot_probability.is_(None),
        AccountProfile.last_analyzed_at.is_(None),
        AccountProfile.last_analyzed_at < cutoff,
    )
    chosen: list = []
    seen: set = set()
    tiers = {"monitoreados": 0, "sin_puntaje": 0, "recalculo": 0}

    def add(rows, tier):
        for p in rows:
            if p.id not in seen and len(chosen) < limit:
                seen.add(p.id)
                chosen.append(p)
                tiers[tier] += 1

    monitored = monitored_author_ids(db)
    if monitored:
        q1 = (db.query(AccountProfile)
                .filter(AccountProfile.id.in_(monitored), data_ok, needs)
                .order_by(AccountProfile.bot_probability.is_(None).desc(),
                          AccountProfile.last_analyzed_at.asc().nullsfirst())
                .limit(limit))
        add(q1.all(), "monitoreados")

    if len(chosen) < limit:
        q2 = db.query(AccountProfile).filter(data_ok, AccountProfile.bot_probability.is_(None))
        if seen:
            q2 = q2.filter(~AccountProfile.id.in_(seen))
        add(q2.limit(limit - len(chosen)).all(), "sin_puntaje")

    if len(chosen) < limit:
        q3 = (db.query(AccountProfile).filter(data_ok, needs))
        if seen:
            q3 = q3.filter(~AccountProfile.id.in_(seen))
        q3 = q3.order_by(AccountProfile.last_analyzed_at.asc().nullsfirst()).limit(limit - len(chosen))
        add(q3.all(), "recalculo")

    return chosen, tiers


# ── Orquestador ────────────────────────────────────────────────────────────

def run_bot_classification(db: Session, limit: int = DEFAULT_BATCH,
                           reanalyze_after_days: int = REANALYZE_AFTER_DAYS) -> dict:
    """
    Califica hasta `limit` cuentas en orden de prioridad (ver select_profiles_to_analyze).
    Llamado por la tarea Celery (cada hora).
    """
    profiles, tiers = select_profiles_to_analyze(db, limit, reanalyze_after_days)
    if not profiles:
        return {"status": "ok", "analyzed": 0, "bots": 0, "suspicious": 0, "tiers": tiers}

    # Análisis existentes de este lote (uno por cuenta; si hubiera duplicados históricos, el más reciente)
    ids = [p.id for p in profiles]
    existing_by_profile = {
        a.account_profile_id: a
        for a in (db.query(BotAnalysis)
                    .filter(BotAnalysis.account_profile_id.in_(ids))
                    .order_by(BotAnalysis.analyzed_at.asc())
                    .all())
    }

    analyzed = bots = suspicious = errors = 0
    for profile in profiles:
        try:
            analysis = analyze_account(db, profile, existing_by_profile.get(profile.id))
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
        "status":     "ok",
        "analyzed":   analyzed,
        "bots":       bots,
        "suspicious": suspicious,
        "errors":     errors,
        "tiers":      tiers,
        "model":      "ml_v2" if _MODEL_CACHE else HEURISTIC_VERSION,
    }
    logger.info(f"[BotML] Completado: {summary}")
    return summary
