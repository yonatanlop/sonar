"""
Generador de Keywords por Tema (IA) — API.
================================================
Genera expresiones de búsqueda booleanas a partir de un tema usando Groq,
y permite guardarlas como keywords de una entidad o como términos del
buscador global de Twitter. También dispara una búsqueda en vivo.

Accesible para analistas y administradores (require_analyst).
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_analyst
from app.database import get_db
from app.models.entity import Entity, Keyword
from app.models.twitter_keyword import TwitterKeywordConfig, TwitterKeywordTerm
from app.models.user import User

router = APIRouter(prefix="/topic-keywords", tags=["Generador de Keywords por Tema"])

VALID_OPS = {"AND", "OR", "NOT"}


# ── Schemas ───────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    topic: str
    intent: Optional[str] = ""
    max_keywords: int = 8


class KeywordItem(BaseModel):
    expression: str
    terms: List[str]
    ops: List[str] = []
    language: str = "es"
    weight: int = 1


class SaveRequest(BaseModel):
    keywords: List[KeywordItem]


# ── Helpers ───────────────────────────────────────────────────

def _keyword_fields(item: KeywordItem) -> dict:
    """
    Mapea una expresión generada a los campos del modelo Keyword,
    siguiendo el mismo criterio que entities.py:
      - 1 término  → keyword simple
      - 2 términos → keyword + keyword_secondary + logic_op
      - 3+ términos → keyword_expression con la expresión completa
    """
    terms = [t.strip() for t in item.terms if t.strip()]
    ops = [o.strip().upper() for o in item.ops if o.strip().upper() in VALID_OPS]

    fields = {
        "keyword": terms[0] if terms else item.expression.strip(),
        "keyword_secondary": None,
        "logic_op": "AND",
        "keyword_expression": None,
        "language": item.language or "es",
        "weight": item.weight or 1,
    }
    if len(terms) == 2:
        fields["keyword_secondary"] = terms[1]
        fields["logic_op"] = ops[0] if ops else "AND"
    elif len(terms) > 2:
        fields["keyword_expression"] = item.expression.strip()
    return fields


def _term_extra_conditions(item: KeywordItem) -> tuple[Optional[str], str, Optional[list]]:
    """
    Mapea una expresión a (secondary_term, logic_op, extra_conditions)
    para el modelo TwitterKeywordTerm.
    """
    terms = [t.strip() for t in item.terms if t.strip()]
    ops = [o.strip().upper() for o in item.ops if o.strip().upper() in VALID_OPS]

    if len(terms) <= 1:
        return None, "AND", None
    if len(terms) == 2:
        return terms[1], (ops[0] if ops else "AND"), None
    # 3+ términos → extra_conditions [{term, op}] para cada término después del primero
    extra = []
    for i, t in enumerate(terms[1:]):
        op = ops[i] if i < len(ops) else "AND"
        extra.append({"term": t, "op": op})
    return None, "AND", extra


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/generate")
def generate_keywords(
    data: GenerateRequest,
    _: User = Depends(require_analyst),
):
    """Genera expresiones de keywords booleanas a partir de un tema usando IA."""
    from app.workers.agents.topic_keyword_generator import generate_keywords_from_topic
    try:
        results = generate_keywords_from_topic(
            topic=data.topic,
            intent=data.intent or "",
            max_keywords=data.max_keywords,
        )
        return {"keywords": results, "count": len(results)}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/save-to-entity/{entity_id}")
def save_to_entity(
    entity_id: uuid.UUID,
    data: SaveRequest,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_db),
):
    """Guarda las keywords generadas como keywords de una entidad."""
    if not db.query(Entity).filter(Entity.id == entity_id).first():
        raise HTTPException(status_code=404, detail="Entidad no encontrada")
    if not data.keywords:
        raise HTTPException(status_code=422, detail="No hay keywords para guardar")

    saved = 0
    for item in data.keywords:
        fields = _keyword_fields(item)
        if not fields["keyword"]:
            continue
        kw = Keyword(entity_id=entity_id, created_by=current_user.id, **fields)
        db.add(kw)
        saved += 1
    db.commit()
    return {"saved": saved, "target": "entity", "entity_id": str(entity_id)}


@router.post("/save-global")
def save_global(
    data: SaveRequest,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_db),
):
    """Guarda las keywords generadas como términos del buscador global de Twitter."""
    if not data.keywords:
        raise HTTPException(status_code=422, detail="No hay keywords para guardar")

    saved = 0
    skipped = 0
    for item in data.keywords:
        terms = [t.strip() for t in item.terms if t.strip()]
        primary = terms[0] if terms else item.expression.strip()
        if not primary:
            continue
        term_type = "hashtag" if primary.startswith("#") else "keyword"
        secondary, logic_op, extra = _term_extra_conditions(item)

        # Evitar duplicados (mismo term + secondary + tipo)
        existing = db.query(TwitterKeywordTerm).filter(
            TwitterKeywordTerm.term == primary,
            TwitterKeywordTerm.secondary_term == secondary,
            TwitterKeywordTerm.term_type == term_type,
        ).first()
        if existing:
            if not existing.is_active:
                existing.is_active = True
                saved += 1
            else:
                skipped += 1
            continue

        t = TwitterKeywordTerm(
            term=primary,
            term_type=term_type,
            secondary_term=secondary if not extra else None,
            logic_op=logic_op,
            extra_conditions=extra,
            is_active=True,
            created_by_id=current_user.id,
        )
        db.add(t)
        saved += 1
    db.commit()
    return {"saved": saved, "skipped": skipped, "target": "global"}


@router.post("/live-search")
def live_search(
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_db),
):
    """
    Dispara una búsqueda en vivo en Twitter/X con los términos globales activos.
    Activa la configuración global si estaba apagada (la búsqueda es no-op sin ella).
    """
    active_terms = db.query(TwitterKeywordTerm).filter(
        TwitterKeywordTerm.is_active == True
    ).count()
    if active_terms == 0:
        raise HTTPException(
            status_code=422,
            detail="No hay términos globales activos. Guarda keywords en modo Global primero.",
        )

    config = db.query(TwitterKeywordConfig).first()
    if not config:
        config = TwitterKeywordConfig(is_active=True)
        db.add(config)
    if not config.is_active:
        config.is_active = True
        config.activated_at = datetime.now(timezone.utc)
        config.stopped_at = None
        config.activated_by_id = current_user.id
    db.commit()

    from app.workers.tasks.scraping import search_twitter_keywords
    task = search_twitter_keywords.delay()
    return {
        "ok": True,
        "task_id": task.id,
        "active_terms": active_terms,
        "message": "Búsqueda iniciada en Twitter/X — resultados en ~1 minuto",
    }
