"""
Generación de Embeddings Semánticos — Módulo 6.1 v2

Usa HuggingFace Inference API con el modelo
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dims, es+en).
Sin PyTorch local — mantiene el Docker liviano.

Flujo:
  - Tarea Celery `generate_embeddings` corre cada 30 min.
  - Procesa hasta BATCH_PER_RUN menciones sin embedding (más recientes primero).
  - Espera DELAY_SECS entre llamadas para respetar el free tier de HF (~1 000 req/día).
  - La búsqueda semántica usa similitud coseno vía pgvector (<=>).
"""
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

HF_MODEL         = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
HF_EMBED_URL     = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
BATCH_PER_RUN    = 15       # max menciones por ejecución (conserva free tier)
DELAY_SECS       = 2.0      # pausa entre llamadas a HF API
MAX_TEXT_CHARS   = 512      # truncar texto antes de enviar


# ── Generación de embedding via HF API ───────────────────────────

def get_embedding(text: str, token: str) -> list[float] | None:
    """
    Llama a HuggingFace Inference API y retorna vector 384 dims.
    Retorna None si hay error o el token no está configurado.
    """
    if not token or not text:
        return None

    text_clean = text.strip()[:MAX_TEXT_CHARS]

    try:
        response = httpx.post(
            HF_EMBED_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"inputs": text_clean, "options": {"wait_for_model": True}},
            timeout=45,
        )

        if response.status_code == 503:
            # Modelo iniciando — esperar y reintentar una vez
            time.sleep(20)
            response = httpx.post(
                HF_EMBED_URL,
                headers={"Authorization": f"Bearer {token}"},
                json={"inputs": text_clean, "options": {"wait_for_model": True}},
                timeout=45,
            )

        if response.status_code != 200:
            logger.warning(f"[Embeddings] HF API status {response.status_code}: {response.text[:100]}")
            return None

        result = response.json()

        # HF puede retornar [[emb]] o [emb] según el modelo
        if isinstance(result, list) and result:
            if isinstance(result[0], list):
                return result[0]   # [[384 floats]] → [384 floats]
            if isinstance(result[0], float):
                return result      # ya es [384 floats]

        return None

    except Exception as exc:
        logger.warning(f"[Embeddings] Error al llamar HF API: {exc}")
        return None


# ── Búsqueda semántica ────────────────────────────────────────────

def semantic_search(db, query_text: str, token: str,
                    entity_id=None, limit: int = 20) -> list[dict]:
    """
    Genera embedding para `query_text` y busca las menciones más similares
    por distancia coseno (pgvector). Retorna lista de dicts con similarity score.
    """
    from app.models.mention import Mention
    from app.models.entity import Entity
    from app.models.mention import SocialPlatform

    query_emb = get_embedding(query_text, token)
    if query_emb is None:
        return []

    try:
        from pgvector.sqlalchemy import cosine_distance

        q = (
            db.query(
                Mention,
                cosine_distance(Mention.embedding, query_emb).label("distance"),
            )
            .filter(Mention.embedding.isnot(None))
        )

        if entity_id:
            q = q.filter(Mention.entity_id == entity_id)

        results = (
            q.order_by("distance")
            .limit(limit)
            .all()
        )

        items = []
        for mention, distance in results:
            similarity = round(1.0 - float(distance), 4)
            if similarity < 0.3:   # filtrar resultados muy poco relevantes
                continue

            platform = db.query(SocialPlatform).filter(SocialPlatform.id == mention.platform_id).first()
            entity   = db.query(Entity).filter(Entity.id == mention.entity_id).first()

            items.append({
                "id":              str(mention.id),
                "entity_name":     entity.name if entity else "—",
                "platform_code":   platform.code if platform else None,
                "platform_name":   platform.name if platform else None,
                "content":         mention.content,
                "author_username": mention.author_username,
                "url":             mention.url,
                "published_at":    mention.published_at.isoformat() if mention.published_at else None,
                "sentiment_label": mention.sentiment_label,
                "urgency_score":   float(mention.urgency_score) if mention.urgency_score is not None else 0,
                "similarity":      similarity,
            })

        return items

    except Exception as exc:
        logger.error(f"[Embeddings] Error en búsqueda semántica: {exc}", exc_info=True)
        return []


# ── Generación batch ──────────────────────────────────────────────

def run_embedding_generation(db) -> dict:
    """
    Genera embeddings para menciones recientes sin embedding.
    Llamado por la tarea Celery cada 30 minutos.
    """
    from app.core.config import settings
    from app.models.mention import Mention

    if not settings.HUGGINGFACE_TOKEN:
        return {"status": "skipped", "reason": "no_hf_token"}

    since = datetime.now(timezone.utc) - timedelta(days=30)

    # Menciones procesadas, recientes, sin embedding
    mentions = (
        db.query(Mention)
        .filter(
            Mention.processed    == True,
            Mention.collected_at >= since,
            Mention.embedding    == None,  # noqa: E711
        )
        .order_by(Mention.collected_at.desc())
        .limit(BATCH_PER_RUN)
        .all()
    )

    generated = 0
    errors    = 0

    for mention in mentions:
        text = mention.content_clean or mention.content or ""
        emb  = get_embedding(text, settings.HUGGINGFACE_TOKEN)
        if emb:
            mention.embedding = emb
            generated += 1
        else:
            errors += 1
        time.sleep(DELAY_SECS)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"[Embeddings] Error en commit: {exc}", exc_info=True)

    result = {
        "generated": generated,
        "errors":    errors,
        "total":     len(mentions),
    }
    logger.info(f"[Embeddings] {result}")
    return result
