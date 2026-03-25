"""
Detección de idioma para menciones.

Estrategia:
  1. langdetect  — rápido, 55 idiomas, suficiente para textos largos
  2. lingua-py   — más preciso en textos cortos (<20 palabras)
  3. Fallback    — 'es' si no se puede determinar

Idiomas soportados actualmente: es, en
Idiomas futuros: pt, fr (basta con agregarlos a LINGUA_LANGUAGES)
"""
import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {"es", "en", "pt", "fr"}
SHORT_TEXT_THRESHOLD = 20   # palabras — si tiene menos, usar lingua-py


@lru_cache(maxsize=1)
def _get_lingua_detector():
    """Carga lingua-py una sola vez (lazy, hilo-seguro por lru_cache)."""
    try:
        from lingua import Language, LanguageDetectorBuilder
        languages = [
            Language.SPANISH,
            Language.ENGLISH,
            Language.PORTUGUESE,
            Language.FRENCH,
        ]
        return LanguageDetectorBuilder.from_languages(*languages).build()
    except ImportError:
        logger.warning("lingua-language-detector no instalada. Solo se usará langdetect.")
        return None


_LINGUA_CODE = {
    "SPANISH":    "es",
    "ENGLISH":    "en",
    "PORTUGUESE": "pt",
    "FRENCH":     "fr",
}


def detect_language(text: str) -> str:
    """
    Detecta el idioma de un texto.
    Retorna código ISO 639-1 de 2 letras ('es', 'en', etc.)
    o 'es' como fallback.
    """
    if not text or len(text.strip()) < 5:
        return "es"

    word_count = len(text.split())

    # Textos cortos → lingua-py (más preciso)
    if word_count < SHORT_TEXT_THRESHOLD:
        lang = _detect_lingua(text)
        if lang:
            return lang

    # Textos largos → langdetect (más rápido)
    lang = _detect_langdetect(text)
    if lang:
        return lang

    # Fallback a lingua-py si langdetect falló
    lang = _detect_lingua(text)
    return lang or "es"


def _detect_langdetect(text: str) -> Optional[str]:
    try:
        from langdetect import detect, LangDetectException
        lang = detect(text)
        # Solo retornar si es un idioma que manejamos o uno conocido
        return lang[:2] if lang else None
    except Exception:
        return None


def _detect_lingua(text: str) -> Optional[str]:
    try:
        detector = _get_lingua_detector()
        if not detector:
            return None
        result = detector.detect_language_of(text)
        if result is None:
            return None
        # result.name es "SPANISH", "ENGLISH", etc.
        return _LINGUA_CODE.get(result.name)
    except Exception:
        return None


def is_supported_language(lang: str) -> bool:
    return lang in SUPPORTED_LANGUAGES
