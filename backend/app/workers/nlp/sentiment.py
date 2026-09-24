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
MODEL_ES   = "pysentimiento/robertuito-sentiment-analysis"   # solo modo 'local'
MODEL_EN   = "cardiffnlp/twitter-roberta-base-sentiment-latest"
MODEL_MULTI = "nlptown/bert-base-multilingual-uncased-sentiment"   # solo modo 'local' (estrellas, poco fiable)
# Modo 'api': español y demás idiomas. Multilingüe (XLM-R), entrenado en tweets, 3 clases
# (negative/neutral/positive). robertuito ya no está disponible en la Inference API de HF
# ("Model not supported by provider hf-inference"), y el respaldo anterior (nlptown, estrellas
# de reseñas de producto) polarizaba todo: 1★→muy negativo, 4-5★→positivo.
MODEL_XLMR = "cardiffnlp/twitter-xlm-roberta-base-sentiment"

# Confianza mínima para aceptar una etiqueta. Por debajo, la mención queda "sin clasificar"
# (sentiment_label = NULL) en vez de guardar como cierta una predicción débil.
MIN_CONFIDENCE = 0.60

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


def _analyze_api(text: str, lang: str) -> Optional[dict]:
    """Sentimiento vía HF Inference API. Retorna None si el servicio no respondió.

    Inglés → cardiffnlp roberta; resto (incl. español) → XLM-R multilingüe. Ambos devuelven
    negative/neutral/positive, así que comparten normalización. Ya NO se cae a nlptown ni se
    devuelve "neutral 0.5" si todo falla: un fallo del servicio se reintenta después en vez
    de guardarse como un neutral falso.
    """
    models = [MODEL_EN, MODEL_XLMR] if lang == "en" else [MODEL_XLMR]
    for model in models:
        result = _hf_api_call(model, text)
        if result:
            # Inference API devuelve [[{label, score}, ...]]
            items = result[0] if isinstance(result[0], list) else result
            return _normalize_en(items)
    return None


# ── Punto de entrada público ──────────────────────────────────

def analyze_sentiment(text: str, lang: str = "es") -> Optional[dict]:
    """
    Analiza el sentimiento de un texto.

    Args:
        text: Texto a analizar (idealmente content_clean de la mención)
        lang: Código de idioma ('es', 'en', 'pt', 'fr', ...)

    Returns:
        {"label": "positive"|"neutral"|"negative"|"very_negative", "score": float}
        o None si el servicio de sentimiento no está disponible (modo 'api').
        El umbral de confianza (MIN_CONFIDENCE) lo aplica quien llama.
    """
    if not text or len(text.strip()) < 3:
        return {"label": "neutral", "score": 0.5}

    if NLP_MODE == "local":
        return _analyze_local(text, lang)
    else:
        return _analyze_api(text, lang)


_LLM_LABELS = ("positive", "neutral", "negative", "very_negative")


def _llm_prompt(text: str, entity_name: str) -> str:
    entity = entity_name or "la entidad monitoreada"
    return (
        'Eres analista de reputación en Colombia. Entidad monitoreada: "' + entity + '".\n'
        "Clasifica el sentimiento de la publicación HACIA esa entidad (no el tono general del texto).\n\n"
        "Criterios:\n"
        "- very_negative: agresión, insulto, difamación o acusación grave contra la entidad.\n"
        "- negative: crítica, denuncia, ironía despectiva o noticia que la perjudica.\n"
        "- neutral: informativo o sin carga hacia la entidad (comunicados, agendas, sesiones, "
        "noticias descriptivas).\n"
        "- positive: apoyo, elogio, agradecimiento o noticia que la favorece "
        "(p. ej. la exoneran o logra algo).\n"
        "Si el texto no habla realmente de la entidad, responde neutral.\n\n"
        'Publicación: """' + text[:600] + '"""\n\n'
        'Responde SOLO un JSON: {"label": "positive|neutral|negative|very_negative", '
        '"confidence": 0.0-1.0}'
    )


def analyze_sentiment_groq(text: str, entity_name: str = "") -> Optional[dict]:
    """
    Sentimiento HACIA la entidad con un LLM de Groq (segunda opinión).

    Se usa cuando el modelo principal (XLM-R) no alcanza la confianza mínima o cuando este
    no está disponible. Devuelve {"label", "score", "source": "groq"} o None si Groq no está
    configurado, falla, o el propio LLM declara una confianza menor a MIN_CONFIDENCE
    (en ese caso la mención sigue "sin clasificar": el umbral se mantiene).
    """
    import json

    from app.core.config import settings
    if not settings.GROQ_API_KEY:
        return None
    try:
        from groq import Groq
    except ImportError:
        logger.debug("Paquete groq no instalado — segunda opinión omitida")
        return None

    model = settings.SENTIMENT_LLM_MODEL
    extra = {"reasoning_effort": "low"} if "gpt-oss" in model else {}
    try:
        client = Groq(api_key=settings.GROQ_API_KEY, timeout=15.0, max_retries=1)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _llm_prompt(text, entity_name)}],
            max_tokens=400,
            temperature=0,
            **extra,
        )
        raw = (response.choices[0].message.content or "").strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            return None
        data = json.loads(raw[start:end + 1])
        label = str(data.get("label", "")).strip().lower()
        confidence = float(data.get("confidence", 0))
        if label not in _LLM_LABELS or confidence < MIN_CONFIDENCE:
            return None
        return {"label": label, "score": round(min(confidence, 1.0), 4), "source": "groq"}
    except Exception as e:
        logger.warning(f"Groq sentimiento ({model}) falló: {e}")
        return None


def classify_text(text: str, lang: str = "es", entity_name_provider=None) -> Optional[dict]:
    """
    Clasificación completa: modelo principal → (si es débil o no responde) LLM de Groq.

    Retorna {"label": str|None, "score": float, "source": "xlmr"|"groq"}; label=None significa
    "sin clasificar". Retorna None solo si NINGÚN servicio pudo responder (se reintenta luego).
    `entity_name_provider` es un callable que devuelve el nombre de la entidad (se invoca solo
    si hace falta la segunda opinión, para evitar consultas innecesarias).
    """
    def _entity() -> str:
        try:
            return (entity_name_provider() if entity_name_provider else "") or ""
        except Exception:
            return ""

    primary = analyze_sentiment(text, lang)
    if primary is None:                       # HF caído → usar el LLM como principal
        return analyze_sentiment_groq(text, _entity())

    label, score = primary["label"], float(primary["score"])
    weak = score < MIN_CONFIDENCE or (label == "neutral" and score < 0.70)
    if weak:
        llm = analyze_sentiment_groq(text, _entity())
        if llm:
            return llm
    return {"label": label if score >= MIN_CONFIDENCE else None, "score": score, "source": "xlmr"}
