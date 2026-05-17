"""
Análisis de sentimiento multi-idioma.

Modelos usados:
  ES → pysentimiento/robertuito-sentiment-analysis   (entrenado en tweets en español)
  EN → cardiffnlp/twitter-roberta-base-sentiment-latest
  XX → nlptown/bert-base-multilingual-uncased-sentiment (fallback multilingual)

Modos de operación (seleccionado por variable de entorno NLP_MODE):
  'local'    — carga modelos en RAM (requiere ~2GB+ RAM, recomendado en Oracle Cloud)
  'api'      — usa HuggingFace Inference API HTTP (gratis con token, sin RAM local)
               ideal para Railway/Fly.io con poca memoria

Salida normalizada:
  { "label": "positive"|"neutral"|"negative"|"very_negative", "score": float 0-1 }
"""
import logging
import os
import time
from functools import lru_cache
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

NLP_MODE = os.getenv("NLP_MODE", "api")   # 'local' | 'api'

# ── Modelos ───────────────────────────────────────────────────
MODEL_ES   = "pysentimiento/robertuito-sentiment-analysis"
MODEL_EN   = "cardiffnlp/twitter-roberta-base-sentiment-latest"
MODEL_MULTI = "nlptown/bert-base-multilingual-uncased-sentiment"

HF_API_BASE = "https://router.huggingface.co/hf-inference/models"

# Truncar texto a este límite antes de enviar al modelo
MAX_TOKENS = 512
MAX_CHARS  = 1000


# ── Carga lazy de modelos locales ─────────────────────────────

@lru_cache(maxsize=1)
def _load_pipeline_es():
    from transformers import pipeline
    logger.info(f"Cargando modelo ES: {MODEL_ES}")
    return pipeline("text-classification", model=MODEL_ES, top_k=None)


@lru_cache(maxsize=1)
def _load_pipeline_en():
    from transformers import pipeline
    logger.info(f"Cargando modelo EN: {MODEL_EN}")
    return pipeline("text-classification", model=MODEL_EN, top_k=None)


@lru_cache(maxsize=1)
def _load_pipeline_multi():
    from transformers import pipeline
    logger.info(f"Cargando modelo multilingual: {MODEL_MULTI}")
    return pipeline("text-classification", model=MODEL_MULTI)


# ── Normalización de resultados ───────────────────────────────

def _normalize_es(results: list) -> dict:
    """
    pysentimiento devuelve: [{'label': 'POS'/'NEU'/'NEG', 'score': float}]
    Muy negativo si NEG score > 0.85.
    """
    scores = {r["label"]: r["score"] for r in results}
    neg_score = scores.get("NEG", 0.0)
    pos_score = scores.get("POS", 0.0)
    neu_score = scores.get("NEU", 0.0)

    if neg_score >= 0.85:
        label = "very_negative"
    elif neg_score > pos_score and neg_score > neu_score:
        label = "negative"
    elif pos_score > neu_score:
        label = "positive"
    else:
        label = "neutral"

    # score normalizado: diferencia entre la emoción dominante y las demás
    dominant_score = max(neg_score, pos_score, neu_score)
    return {"label": label, "score": round(dominant_score, 4)}


def _normalize_en(results: list) -> dict:
    """
    cardiffnlp devuelve: [{'label': 'positive'/'neutral'/'negative', 'score': float}]
    """
    scores = {r["label"].lower(): r["score"] for r in results}
    neg = scores.get("negative", 0.0)
    pos = scores.get("positive", 0.0)
    neu = scores.get("neutral",  0.0)

    if neg >= 0.85:
        label = "very_negative"
    elif neg > pos and neg > neu:
        label = "negative"
    elif pos > neu:
        label = "positive"
    else:
        label = "neutral"

    return {"label": label, "score": round(max(neg, pos, neu), 4)}


def _normalize_multi(result) -> dict:
    """
    nlptown devuelve: {'label': '1 star'...'5 stars', 'score': float}
    1-2 stars → negative/very_negative, 3 → neutral, 4-5 → positive
    """
    label_str = result["label"] if isinstance(result, dict) else result[0]["label"]
    score     = result["score"] if isinstance(result, dict) else result[0]["score"]

    stars = int(label_str.split()[0])
    if stars == 1:
        label = "very_negative"
    elif stars == 2:
        label = "negative"
    elif stars == 3:
        label = "neutral"
    else:
        label = "positive"

    return {"label": label, "score": round(float(score), 4)}


# ── Análisis local ────────────────────────────────────────────

def _analyze_local(text: str, lang: str) -> dict:
    text = text[:MAX_CHARS]
    try:
        if lang == "es":
            pipe    = _load_pipeline_es()
            results = pipe(text)[0]
            return _normalize_es(results)
        elif lang == "en":
            pipe    = _load_pipeline_en()
            results = pipe(text)[0]
            return _normalize_en(results)
        else:
            pipe   = _load_pipeline_multi()
            result = pipe(text)
            return _normalize_multi(result)
    except Exception as e:
        logger.error(f"Error en análisis local (lang={lang}): {e}")
        return _analyze_multi_local(text)


def _analyze_multi_local(text: str) -> dict:
    try:
        pipe   = _load_pipeline_multi()
        result = pipe(text[:MAX_CHARS])
        return _normalize_multi(result)
    except Exception as e:
        logger.error(f"Error en modelo multilingual: {e}")
        return {"label": "neutral", "score": 0.5}


# ── Análisis vía HuggingFace Inference API ────────────────────

def _hf_api_call(model: str, text: str) -> Optional[list]:
    """Llama a la Inference API de HuggingFace. Retorna None si falla."""
    from app.core.config import settings
    if not settings.HUGGINGFACE_TOKEN:
        return None
    try:
        resp = httpx.post(
            f"{HF_API_BASE}/{model}",
            headers={"Authorization": f"Bearer {settings.HUGGINGFACE_TOKEN}"},
            json={"inputs": text[:MAX_CHARS]},
            timeout=15.0,
        )
        if resp.status_code == 503:
            # Modelo cargándose — esperar y reintentar una vez
            time.sleep(10)
            resp = httpx.post(
                f"{HF_API_BASE}/{model}",
                headers={"Authorization": f"Bearer {settings.HUGGINGFACE_TOKEN}"},
                json={"inputs": text[:MAX_CHARS]},
                timeout=20.0,
            )
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"HF API {model} → HTTP {resp.status_code}")
        return None
    except Exception as e:
        logger.warning(f"HF API error ({model}): {e}")
        return None


def _analyze_api(text: str, lang: str) -> dict:
    if lang == "es":
        result = _hf_api_call(MODEL_ES, text)
        if result:
            # Inference API devuelve [[{label, score}, ...]]
            items = result[0] if isinstance(result[0], list) else result
            return _normalize_es(items)

    elif lang == "en":
        result = _hf_api_call(MODEL_EN, text)
        if result:
            items = result[0] if isinstance(result[0], list) else result
            return _normalize_en(items)

    # Fallback multilingual
    result = _hf_api_call(MODEL_MULTI, text)
    if result:
        items = result[0] if isinstance(result[0], list) else result
        return _normalize_multi(items[0] if isinstance(items, list) else items)

    # Si todo falla, retornar neutral
    return {"label": "neutral", "score": 0.5}


# ── Punto de entrada público ──────────────────────────────────

def analyze_sentiment(text: str, lang: str = "es") -> dict:
    """
    Analiza el sentimiento de un texto.

    Args:
        text: Texto a analizar (idealmente content_clean de la mención)
        lang: Código de idioma ('es', 'en', 'pt', 'fr', ...)

    Returns:
        {"label": "positive"|"neutral"|"negative"|"very_negative", "score": float}
    """
    if not text or len(text.strip()) < 3:
        return {"label": "neutral", "score": 0.5}

    if NLP_MODE == "local":
        return _analyze_local(text, lang)
    else:
        return _analyze_api(text, lang)


def analyze_sentiment_groq(text: str, entity_name: str = "") -> Optional[dict]:
    """
    Segunda pasada con Groq/Llama para casos dudosos (neutral con baja confianza).

    Solo se llama cuando el modelo principal retornó 'neutral' con score < 0.70.
    Incluye el contexto de la entidad para mejorar precisión en discurso político.

    Returns:
        {"label": ..., "score": 0.80, "source": "groq"} o None si falla/no configurado.
    """
    from app.core.config import settings
    if not settings.GROQ_API_KEY:
        return None
    try:
        from groq import Groq
    except ImportError:
        logger.debug("Paquete groq no instalado — segunda pasada omitida")
        return None

    entity_ctx = f' sobre "{entity_name}"' if entity_name else ""
    prompt = (
        f"Clasifica el sentimiento de esta publicación de redes sociales{entity_ctx}.\n\n"
        f"Texto: \"{text[:600]}\"\n\n"
        f"Criterios:\n"
        f"- very_negative: tono muy agresivo, ofensivo, difamatorio o muy dañino para la reputación\n"
        f"- negative: crítico, acusatorio, de denuncia, irónico negativamente o despectivo\n"
        f"- neutral: informativo sin carga emocional clara\n"
        f"- positive: favorable, de apoyo o elogioso\n\n"
        f"Responde ÚNICAMENTE con una palabra: positive, neutral, negative o very_negative"
    )

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=settings.SUMMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0,
        )
        label = response.choices[0].message.content.strip().lower().rstrip(".")
        if label in ("positive", "neutral", "negative", "very_negative"):
            return {"label": label, "score": 0.80, "source": "groq"}
        return None
    except Exception as e:
        logger.warning(f"Groq second pass error: {e}")
        return None
