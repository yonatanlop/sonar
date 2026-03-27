"""
Módulo 13 — Chat Asistente RAG (Retrieval-Augmented Generation)

Permite hacer preguntas en lenguaje natural sobre las menciones recolectadas.
El sistema busca menciones relevantes y las usa como contexto para que
Llama 3.1 (Groq) genere una respuesta fundamentada en datos reales.

Flujo por consulta:
  1. Embedding de la pregunta (HuggingFace)
  2. Búsqueda semántica en pgvector → top 15 menciones relevantes
  3. Construcción del prompt con contexto enriquecido
  4. Llamada a Groq API (Llama 3.1)
  5. Respuesta en español + fuentes utilizadas

Fases:
  - Fase simple  (CHAT_ADVANCED_MODE=false): cada pregunta es independiente
  - Fase avanzada (CHAT_ADVANCED_MODE=true) : historial multi-turno pasado al LLM
"""
import logging

from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_CONTEXT_MENTIONS = 15   # menciones que se pasan al LLM como contexto
MAX_MENTION_CHARS    = 300  # truncar menciones largas en el prompt


# ── Construcción del prompt ────────────────────────────────────────────────

def _format_mention(m: dict) -> str:
    """Convierte un dict de mención en una línea legible para el LLM."""
    date_str = ""
    if m.get("published_at"):
        date_str = m["published_at"][:10]

    urgency = ""
    score = m.get("urgency_score", 0) or 0
    if score >= 80:
        urgency = " [🔥 CRÍTICO]"
    elif score >= 60:
        urgency = " [⚠️ URGENTE]"
    elif score >= 30:
        urgency = " [👁 ATENCIÓN]"

    sentiment = m.get("sentiment_label", "") or ""
    platform  = m.get("platform_code", "") or ""
    author    = m.get("author_username", "") or ""
    content   = (m.get("content", "") or "").strip()
    if len(content) > MAX_MENTION_CHARS:
        content = content[:MAX_MENTION_CHARS] + "…"

    return (
        f"[{platform}|{date_str}|@{author}|{sentiment}{urgency}] {content}"
    )


def _build_system_prompt() -> str:
    return (
        "Eres MIRA, asistente de inteligencia digital especializado en monitoreo "
        "de redes sociales para IDMJI (Iglesia de Dios Ministerial de Jesucristo Internacional) "
        "y el Partido MIRA de Colombia.\n"
        "Tu función es analizar menciones reales recolectadas de redes sociales y "
        "responder preguntas del equipo de monitoreo.\n"
        "REGLAS:\n"
        "- Responde SIEMPRE en español.\n"
        "- Basa tu respuesta ÚNICAMENTE en las menciones proporcionadas.\n"
        "- Si no hay información suficiente en las menciones, dilo claramente.\n"
        "- Sé específico: cita plataformas, fechas y niveles de urgencia cuando sean relevantes.\n"
        "- No inventes ni supongas información que no esté en las menciones.\n"
        "- Sé conciso y directo — el equipo necesita información accionable."
    )


def _build_user_message(question: str, mentions: list[dict]) -> str:
    if not mentions:
        return (
            f"PREGUNTA: {question}\n\n"
            "CONTEXTO: No se encontraron menciones relevantes en la base de datos "
            "para esta consulta."
        )

    lines = [_format_mention(m) for m in mentions]
    context_block = "\n".join(f"{i+1}. {l}" for i, l in enumerate(lines))

    return (
        f"MENCIONES RELEVANTES ({len(mentions)} encontradas):\n"
        f"{context_block}\n\n"
        f"PREGUNTA: {question}"
    )


# ── Cliente Groq ───────────────────────────────────────────────────────────

def _call_groq(messages: list[dict]) -> str:
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("Paquete 'groq' no instalado.")

    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY no configurada en .env")

    client = Groq(api_key=settings.GROQ_API_KEY)
    response = client.chat.completions.create(
        model=settings.SUMMARY_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()


# ── Punto de entrada principal ─────────────────────────────────────────────

def build_rag_answer(
    db: Session,
    question: str,
    entity_id=None,
    history: list[dict] | None = None,
) -> dict:
    """
    Genera una respuesta basada en menciones reales de la BD.

    Parámetros:
      - question:  pregunta en lenguaje natural
      - entity_id: UUID opcional para filtrar por entidad
      - history:   lista de dicts [{role, content}] para fase avanzada

    Retorna:
      {
        "answer":   str,          # respuesta generada
        "sources":  list[dict],   # menciones utilizadas como contexto
        "found":    int,          # cantidad de menciones encontradas
        "advanced": bool,         # si se usó historial
      }
    """
    if not settings.GROQ_API_KEY:
        return {
            "answer":   "El asistente no está disponible: GROQ_API_KEY no configurada en .env",
            "sources":  [],
            "found":    0,
            "advanced": False,
            "error":    "no_groq_key",
        }

    if not settings.HUGGINGFACE_TOKEN:
        return {
            "answer":   "El asistente no está disponible: HUGGINGFACE_TOKEN no configurado en .env (necesario para búsqueda semántica)",
            "sources":  [],
            "found":    0,
            "advanced": False,
            "error":    "no_hf_token",
        }

    # ── 1. Búsqueda semántica de menciones relevantes ──────────────────────
    from app.workers.nlp.embeddings import semantic_search

    try:
        mentions = semantic_search(
            db, question, settings.HUGGINGFACE_TOKEN,
            entity_id=entity_id,
            limit=MAX_CONTEXT_MENTIONS,
        )
    except Exception as exc:
        logger.error(f"[RAG] Error en búsqueda semántica: {exc}")
        mentions = []

    # ── 2. Construir mensajes para el LLM ──────────────────────────────────
    use_history = (
        settings.CHAT_ADVANCED_MODE
        and history
        and len(history) > 0
    )

    messages = [{"role": "system", "content": _build_system_prompt()}]

    if use_history:
        # Fase avanzada: incluir turnos anteriores
        for turn in history:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    # Añadir pregunta actual con contexto de menciones
    messages.append({
        "role": "user",
        "content": _build_user_message(question, mentions),
    })

    # ── 3. Llamar al LLM ──────────────────────────────────────────────────
    try:
        answer = _call_groq(messages)
    except RuntimeError as exc:
        return {
            "answer":   f"Error al consultar el asistente: {exc}",
            "sources":  mentions,
            "found":    len(mentions),
            "advanced": use_history,
            "error":    "groq_error",
        }
    except Exception as exc:
        logger.error(f"[RAG] Error en Groq: {exc}", exc_info=True)
        return {
            "answer":   "Error interno al procesar la consulta. Intenta de nuevo.",
            "sources":  mentions,
            "found":    len(mentions),
            "advanced": use_history,
            "error":    "internal_error",
        }

    return {
        "answer":   answer,
        "sources":  mentions,
        "found":    len(mentions),
        "advanced": use_history,
    }
