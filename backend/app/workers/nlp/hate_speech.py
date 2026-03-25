"""
Detección de discurso de odio, insultos y ataques dirigidos.

Modelos:
  ES → pysentimiento/robertuito-hate-speech
       Etiquetas: hateful, targeted, aggressive (scores independientes, no excluyentes)

  EN → Hate-speech-CNERG/dehatebert-mono-english
       Etiquetas: hate, noHate

Umbral de decisión: hate_score >= HATE_THRESHOLD → is_hate_speech = True

Modo de operación: mismo NLP_MODE que sentiment.py ('local' | 'api')
"""
import logging
import os
import time
from functools import lru_cache
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

NLP_MODE = os.getenv("NLP_MODE", "api")

MODEL_HATE_ES = "pysentimiento/robertuito-hate-speech"
MODEL_HATE_EN = "Hate-speech-CNERG/dehatebert-mono-english"

HF_API_BASE  = "https://api-inference.huggingface.co/models"
HATE_THRESHOLD = 0.60   # score mínimo para clasificar como discurso de odio
MAX_CHARS      = 512


# ── Carga lazy de modelos locales ─────────────────────────────

@lru_cache(maxsize=1)
def _load_hate_es():
    from transformers import pipeline
    logger.info(f"Cargando modelo hate-speech ES: {MODEL_HATE_ES}")
    return pipeline("text-classification", model=MODEL_HATE_ES, top_k=None)


@lru_cache(maxsize=1)
def _load_hate_en():
    from transformers import pipeline
    logger.info(f"Cargando modelo hate-speech EN: {MODEL_HATE_EN}")
    return pipeline("text-classification", model=MODEL_HATE_EN, top_k=None)


# ── Normalización ─────────────────────────────────────────────

def _normalize_hate_es(results: list) -> dict:
    """
    pysentimiento devuelve lista de dicts con label: 'hateful'|'targeted'|'aggressive'
    Los tres son independientes (multi-label).

    Retorna:
      hate_score  — score de 'hateful' (el más importante)
      is_hate     — True si hate_score >= HATE_THRESHOLD
      indicators  — todos los scores para almacenar en BD
    """
    scores = {r["label"]: round(r["score"], 4) for r in results}
    hate_score = scores.get("hateful", 0.0)
    return {
        "hate_score":  hate_score,
        "is_hate":     hate_score >= HATE_THRESHOLD,
        "indicators": {
            "hateful":    scores.get("hateful",    0.0),
            "targeted":   scores.get("targeted",   0.0),
            "aggressive": scores.get("aggressive", 0.0),
        },
    }


def _normalize_hate_en(results: list) -> dict:
    """
    dehatebert devuelve: [{'label': 'hate'|'noHate', 'score': float}]
    """
    scores = {r["label"].lower(): r["score"] for r in results}
    hate_score = scores.get("hate", 0.0)
    return {
        "hate_score": round(hate_score, 4),
        "is_hate":    hate_score >= HATE_THRESHOLD,
        "indicators": {"hate": hate_score, "no_hate": scores.get("nohate", 0.0)},
    }


# ── Análisis local ────────────────────────────────────────────

def _analyze_local(text: str, lang: str) -> dict:
    text = text[:MAX_CHARS]
    try:
        if lang == "es":
            pipe    = _load_hate_es()
            results = pipe(text)[0]
            return _normalize_hate_es(results)
        else:
            # Para EN y otros idiomas
            pipe    = _load_hate_en()
            results = pipe(text)[0]
            return _normalize_hate_en(results)
    except Exception as e:
        logger.error(f"Error en análisis hate-speech local (lang={lang}): {e}")
        return {"hate_score": 0.0, "is_hate": False, "indicators": {}}


# ── Análisis vía HuggingFace Inference API ────────────────────

def _hf_api_call(model: str, text: str) -> Optional[list]:
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
            time.sleep(10)
            resp = httpx.post(
                f"{HF_API_BASE}/{model}",
                headers={"Authorization": f"Bearer {settings.HUGGINGFACE_TOKEN}"},
                json={"inputs": text[:MAX_CHARS]},
                timeout=20.0,
            )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        logger.warning(f"HF API hate-speech error ({model}): {e}")
        return None


def _analyze_api(text: str, lang: str) -> dict:
    model  = MODEL_HATE_ES if lang == "es" else MODEL_HATE_EN
    result = _hf_api_call(model, text)

    if result:
        items = result[0] if isinstance(result[0], list) else result
        if lang == "es":
            return _normalize_hate_es(items)
        else:
            return _normalize_hate_en(items)

    return {"hate_score": 0.0, "is_hate": False, "indicators": {}}


# ── Punto de entrada público ──────────────────────────────────

def analyze_hate_speech(text: str, lang: str = "es") -> dict:
    """
    Analiza si un texto contiene discurso de odio.

    Args:
        text: Texto a analizar
        lang: Código de idioma ('es', 'en', ...)

    Returns:
        {
            "hate_score": float,   # 0.0 - 1.0
            "is_hate":    bool,    # True si supera HATE_THRESHOLD
            "indicators": dict,    # scores detallados por etiqueta
        }
    """
    if not text or len(text.strip()) < 3:
        return {"hate_score": 0.0, "is_hate": False, "indicators": {}}

    if NLP_MODE == "local":
        return _analyze_local(text, lang)
    else:
        return _analyze_api(text, lang)
