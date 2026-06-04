"""
Agente generador de keywords por tema.
================================================
Dado un tema en lenguaje natural (una cuenta, un personaje, un hashtag o una
palabra) y opcionalmente la intención de búsqueda, usa el LLM de Groq (Llama 3)
para generar varias expresiones de búsqueda booleanas con operadores AND/OR/NOT.

El resultado se puede guardar como keywords de una entidad o como términos del
buscador global de Twitter.
"""
import json
import logging
import re

from app.core.config import settings

logger = logging.getLogger(__name__)

VALID_OPS = {"AND", "OR", "NOT"}
MAX_KEYWORDS_CAP = 12


_SYSTEM_PROMPT = (
    "Eres un experto en monitoreo de redes sociales (OSINT). "
    "Tu tarea es, dado un tema, generar expresiones de búsqueda booleanas "
    "que sirvan para encontrar publicaciones relevantes en redes como "
    "Twitter/X, Facebook, Instagram y YouTube. "
    "Usas operadores lógicos AND, OR y NOT.\n"
    "REGLAS CRÍTICAS:\n"
    "1. El PRIMER término de cada expresión SIEMPRE es el sujeto principal "
    "(el nombre, cuenta, hashtag o palabra del tema). Es obligatorio y ancla la búsqueda.\n"
    "2. Usa OR solo entre SINÓNIMOS o variantes reales del mismo concepto "
    "(p. ej. 'corrupción' OR 'escándalo'), nunca con palabras genéricas como "
    "'gobierno', 'política', 'política pública' que traerían ruido no relacionado.\n"
    "3. TÉRMINOS AMBIGUOS: si el sujeto o un término es un APODO, una palabra común, "
    "o un nombre que también es un animal, equipo, lugar o marca (p. ej. 'Tigre', 'Paloma', "
    "'León'), combínalo SIEMPRE con AND con 1-2 términos de contexto que lo desambigüen "
    "(el tema, el rol, el nombre real). Nunca dejes un apodo ambiguo solo o suelto con OR. "
    "Ejemplo: el apodo 'Tigre' de un político debe ir como "
    "\"Tigre\" AND \"política\" AND \"campaña\" (o con el nombre real) para no traer "
    "tweets del animal ni de fútbol.\n"
    "4. Cuando conozcas el nombre real detrás de un apodo, genera también una expresión "
    "que combine ambos: (apodo OR nombre real) anclados con contexto.\n"
    "5. Usa NOT para excluir ruido concreto (p. ej. NOT 'fútbol', NOT 'zoológico' si el "
    "apodo coincide con un animal).\n"
    "6. NO inventes términos de relleno sin sentido (evita verbos sueltos como "
    "'ignorar', 'descartar', 'sumar', 'involucramiento').\n"
    "7. Prefiere pocas expresiones de ALTA calidad (2-4 términos cada una) antes que muchas vagas.\n"
    "Respondes SIEMPRE y ÚNICAMENTE con un JSON array válido, sin texto adicional."
)


def _build_user_prompt(topic: str, intent: str, max_keywords: int) -> str:
    intent_line = (
        f"El usuario quiere encontrar específicamente: {intent.strip()}\n"
        if intent and intent.strip()
        else ""
    )
    return (
        f"Tema u objetivo a monitorear: {topic.strip()}\n"
        f"{intent_line}"
        f"Genera entre 3 y {max_keywords} expresiones de búsqueda distintas y útiles.\n\n"
        "Cada expresión debe ser un objeto con esta forma EXACTA:\n"
        '{\n'
        '  "expression": "Piraquive AND (corrupción OR escándalo)",\n'
        '  "terms": ["Piraquive", "corrupción", "escándalo"],\n'
        '  "ops": ["AND", "OR"],\n'
        '  "rationale": "Captura menciones del personaje ligadas a controversia"\n'
        '}\n\n'
        "Ejemplo con APODO ambiguo (desambiguado con contexto obligatorio):\n"
        '{\n'
        '  "expression": "Tigre AND política AND campaña",\n'
        '  "terms": ["Tigre", "política", "campaña"],\n'
        '  "ops": ["AND", "AND"],\n'
        '  "rationale": "El apodo Tigre anclado a política y campaña evita el animal o el fútbol"\n'
        '}\n\n'
        "Reglas:\n"
        "- 'terms' es la lista ordenada de términos de la expresión.\n"
        "- 'ops' son los operadores ENTRE términos: tiene exactamente len(terms)-1 elementos, "
        "cada uno es AND, OR o NOT.\n"
        "- 'expression' es la expresión legible completa.\n"
        "- 'rationale' explica en una frase corta qué captura (en español).\n"
        "- Varía el enfoque: algunas amplias (OR de sinónimos), otras específicas (AND con NOT para excluir ruido).\n"
        "- No inventes hechos; solo construye términos de búsqueda.\n\n"
        "Responde SOLO con el JSON array."
    )


def _call_groq(topic: str, intent: str, max_keywords: int) -> str:
    """Llama a Groq y retorna el texto crudo. Lanza excepción si falla."""
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("Paquete 'groq' no instalado. Ejecuta: pip install groq")

    if not settings.GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY no configurada en .env. "
            "Es necesaria para generar keywords con IA."
        )

    client = Groq(api_key=settings.GROQ_API_KEY)
    response = client.chat.completions.create(
        model=settings.SUMMARY_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(topic, intent, max_keywords)},
        ],
        temperature=0.5,    # algo de creatividad para variar las expresiones
        max_tokens=900,
    )
    return response.choices[0].message.content.strip()


def _extract_json_array(text: str) -> list:
    """Extrae el primer array JSON del texto (Llama a veces lo envuelve en prosa)."""
    try:
        return json.loads(text)
    except Exception:
        pass
    # Buscar el primer bloque [...] balanceado
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    raise ValueError("La IA no devolvió un JSON válido.")


def _normalize_item(item: dict) -> dict | None:
    """Valida y normaliza una entrada generada. Retorna None si es inválida."""
    if not isinstance(item, dict):
        return None

    terms = item.get("terms") or []
    terms = [str(t).strip() for t in terms if str(t).strip()]
    if not terms:
        return None

    ops = [str(o).strip().upper() for o in (item.get("ops") or [])]
    # ops debe tener len(terms)-1 elementos válidos
    ops = [o for o in ops if o in VALID_OPS]
    if len(ops) < len(terms) - 1:
        # rellenar con AND si la IA mandó menos operadores de los necesarios
        ops += ["AND"] * (len(terms) - 1 - len(ops))
    ops = ops[: max(0, len(terms) - 1)]

    # Reconstruir expression si falta o es inconsistente
    expression = str(item.get("expression") or "").strip()
    if not expression:
        parts = [terms[0]]
        for i, op in enumerate(ops):
            parts.append(op)
            parts.append(terms[i + 1])
        expression = " ".join(parts)

    rationale = str(item.get("rationale") or "").strip()

    return {
        "expression": expression,
        "terms": terms,
        "ops": ops,
        "rationale": rationale,
    }


def generate_keywords_from_topic(
    topic: str,
    intent: str = "",
    max_keywords: int = 8,
) -> list[dict]:
    """
    Genera expresiones de keywords booleanas a partir de un tema.

    Retorna lista de dicts: {expression, terms, ops, rationale}.
    Lanza ValueError si no hay GROQ_API_KEY o si la IA no devuelve algo usable.
    """
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("El tema no puede estar vacío.")

    max_keywords = max(3, min(int(max_keywords or 8), MAX_KEYWORDS_CAP))

    raw = _call_groq(topic, intent, max_keywords)
    data = _extract_json_array(raw)

    if not isinstance(data, list):
        raise ValueError("La IA no devolvió una lista de keywords.")

    results = []
    for item in data:
        norm = _normalize_item(item)
        if norm:
            results.append(norm)

    if not results:
        raise ValueError("La IA no generó keywords válidas. Intenta reformular el tema.")

    return results[:max_keywords]
