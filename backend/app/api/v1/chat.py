"""
Módulo 13 — Chat Asistente RAG
Endpoints:
  GET  /chat/config  → estado del asistente y modo activo
  POST /chat         → enviar pregunta, recibir respuesta fundamentada
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.database import get_db

router = APIRouter(prefix="/chat", tags=["Chat Asistente"])


# ── Schemas ────────────────────────────────────────────────────────────────

class HistoryItem(BaseModel):
    role: str     # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    question: str
    entity_id: Optional[uuid.UUID] = None
    history:   Optional[list[HistoryItem]] = None   # solo se usa si CHAT_ADVANCED_MODE=true


class ChatResponse(BaseModel):
    answer:   str
    sources:  list[dict]
    found:    int
    advanced: bool
    error:    Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/config")
def chat_config(_=Depends(get_current_user)):
    """
    Devuelve la configuración actual del asistente:
    - available:      si Groq y HuggingFace están configurados
    - advanced_mode:  si el historial multi-turno está activo
    """
    return {
        "available":     bool(settings.GROQ_API_KEY and settings.HUGGINGFACE_TOKEN),
        "advanced_mode": settings.CHAT_ADVANCED_MODE,
        "model":         settings.SUMMARY_MODEL,
    }


@router.post("", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Recibe una pregunta en lenguaje natural, busca menciones relevantes
    mediante búsqueda semántica y genera una respuesta con Llama 3.1 (Groq).

    En fase simple (CHAT_ADVANCED_MODE=false) el campo `history` se ignora.
    En fase avanzada (CHAT_ADVANCED_MODE=true) el historial se incluye en el contexto.
    """
    from app.workers.nlp.rag import build_rag_answer

    history = (
        [h.model_dump() for h in req.history]
        if req.history else None
    )

    result = build_rag_answer(
        db=db,
        question=req.question,
        entity_id=req.entity_id,
        history=history,
    )

    return ChatResponse(**result)
