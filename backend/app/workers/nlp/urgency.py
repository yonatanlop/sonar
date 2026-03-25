"""
Módulo de Urgency Score — v2

Calcula un score 0-100 que refleja cuán urgente/crítica es una mención,
combinando tres señales ya disponibles tras el pipeline NLP:

  sentimiento  (35 %) — qué tan negativo es el contenido
  hate speech  (35 %) — probabilidad de discurso de odio
  alcance      (30 %) — cuántas interacciones generó (reach)

Escala de interpretación:
  0  – 29  → verde  (baja urgencia, monitoreo normal)
  30 – 59  → naranja (urgencia media, atención recomendada)
  60 – 79  → rojo claro (urgencia alta, revisar pronto)
  80 – 100 → rojo intenso (crítico, acción inmediata)
"""
import math


# ── Pesos ──────────────────────────────────────────────────────────────────
_W_SENTIMENT = 0.35
_W_HATE      = 0.35
_W_REACH     = 0.30

# Reach de referencia para normalización logarítmica:
# reach=0 → 0 pts, reach≥REACH_MAX → 100 pts
_REACH_MAX = 10_000


def _sentiment_component(label: str | None, score: float | None) -> float:
    """
    Convierte el par (label, score) del sentimiento en un valor 0-100.

    El score del modelo HuggingFace viene como probabilidad de la clase,
    no como dirección del sentimiento. Lo usamos para graduar la severidad
    dentro de cada etiqueta.
    """
    if label is None:
        return 0.0

    # Base por etiqueta
    base = {
        "very_negative": 100.0,
        "negative":       65.0,
        "neutral":        15.0,
        "positive":        0.0,
    }.get(label, 0.0)

    # Para etiquetas negativas, el score de confianza amplifica ligeramente
    # Ej: negative con score=0.95 → 65 * (1 + 0.15 * 0.95) ≈ 74
    if label in ("negative", "very_negative") and score is not None:
        confidence_boost = 0.15 * float(score)
        base = min(base * (1 + confidence_boost), 100.0)

    return base


def _hate_component(hate_score: float | None, is_hate: bool) -> float:
    """
    Convierte el hate_score (0-1) en valor 0-100.
    Si is_hate_speech=True se aplica un multiplicador adicional.
    """
    if hate_score is None:
        return 0.0

    base = float(hate_score) * 100.0

    # Si el modelo ya clasificó como hate speech, elevar el piso mínimo a 60
    if is_hate and base < 60.0:
        base = 60.0

    return min(base, 100.0)


def _reach_component(reach: int) -> float:
    """
    Normaliza el reach con escala logarítmica para que valores extremos
    no dominen el score total.

    reach=0       →  0.0
    reach=100     → ~40.0
    reach=1_000   → ~60.0
    reach=10_000  → ~80.0
    reach=100_000 → ~100.0
    """
    if not reach or reach <= 0:
        return 0.0

    # log10(1) = 0, log10(REACH_MAX+1) ≈ 4
    max_log = math.log10(_REACH_MAX + 1)
    val     = math.log10(reach + 1) / max_log
    return min(val * 100.0, 100.0)


def compute_urgency_score(
    sentiment_label: str | None,
    sentiment_score: float | None,
    hate_score: float | None,
    is_hate_speech: bool,
    reach: int,
) -> float:
    """
    Función principal. Devuelve un float redondeado a 1 decimal en [0, 100].

    Uso desde el pipeline NLP:
        score = compute_urgency_score(
            mention.sentiment_label,
            float(mention.sentiment_score) if mention.sentiment_score else None,
            float(mention.hate_score)      if mention.hate_score      else None,
            mention.is_hate_speech,
            mention.reach,
        )
        mention.urgency_score = score
    """
    s = _sentiment_component(sentiment_label, sentiment_score)
    h = _hate_component(hate_score, is_hate_speech)
    r = _reach_component(reach)

    raw = s * _W_SENTIMENT + h * _W_HATE + r * _W_REACH
    return round(max(0.0, min(raw, 100.0)), 1)


def urgency_level(score: float) -> str:
    """
    Etiqueta legible para el score.
    Usada en el frontend y en notificaciones.
    """
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"
