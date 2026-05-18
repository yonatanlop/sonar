"""
Búsqueda Twitter por Keyword/Hashtag — API de configuración y control.
Solo accesible para administradores.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.twitter_keyword import TwitterKeywordConfig, TwitterKeywordTerm
from app.models.user import User

router = APIRouter(prefix="/twitter-keyword-search", tags=["Twitter Keyword Search"])


# ── Schemas ───────────────────────────────────────────────────

class TermCreate(BaseModel):
    term:      str
    term_type: str   # 'keyword' | 'hashtag'


class TermResponse(BaseModel):
    id:        int
    term:      str
    term_type: str
    is_active: bool
    created_at: Optional[str]


class StatusResponse(BaseModel):
    is_active:    bool
    activated_at: Optional[str]
    stopped_at:   Optional[str]
    last_run_at:  Optional[str]
    active_terms: int
    total_terms:  int


# ── Helpers ───────────────────────────────────────────────────

def _term_dict(t: TwitterKeywordTerm) -> dict:
    return {
        "id":        t.id,
        "term":      t.term,
        "term_type": t.term_type,
        "is_active": t.is_active,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _config_status(db: Session) -> dict:
    config = db.query(TwitterKeywordConfig).first()
    active_terms = db.query(TwitterKeywordTerm).filter(TwitterKeywordTerm.is_active == True).count()
    total_terms  = db.query(TwitterKeywordTerm).count()
    if not config:
        return {
            "is_active":    False,
            "activated_at": None,
            "stopped_at":   None,
            "last_run_at":  None,
            "active_terms": active_terms,
            "total_terms":  total_terms,
        }
    return {
        "is_active":    config.is_active,
        "activated_at": config.activated_at.isoformat()  if config.activated_at else None,
        "stopped_at":   config.stopped_at.isoformat()    if config.stopped_at   else None,
        "last_run_at":  config.last_run_at.isoformat()   if config.last_run_at  else None,
        "active_terms": active_terms,
        "total_terms":  total_terms,
    }


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/status")
def get_status(
    db: Session = Depends(get_db),
    _:  User    = Depends(require_admin),
):
    """Retorna el estado actual de la búsqueda y estadísticas de términos."""
    return _config_status(db)


@router.get("/terms")
def list_terms(
    db: Session = Depends(get_db),
    _:  User    = Depends(require_admin),
):
    """Lista todos los términos configurados (activos e inactivos)."""
    terms = db.query(TwitterKeywordTerm).order_by(TwitterKeywordTerm.created_at).all()
    return [_term_dict(t) for t in terms]


@router.post("/terms", status_code=status.HTTP_201_CREATED)
def add_term(
    data: TermCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(require_admin),
):
    """Agrega un nuevo keyword o hashtag a la lista de búsqueda."""
    if data.term_type not in ("keyword", "hashtag"):
        raise HTTPException(status_code=422, detail="term_type debe ser 'keyword' o 'hashtag'")

    term_clean = data.term.strip()
    if not term_clean:
        raise HTTPException(status_code=422, detail="El término no puede estar vacío")

    # Evitar duplicados (por term + term_type)
    existing = db.query(TwitterKeywordTerm).filter(
        TwitterKeywordTerm.term      == term_clean,
        TwitterKeywordTerm.term_type == data.term_type,
    ).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.commit()
            return _term_dict(existing)
        raise HTTPException(status_code=409, detail=f"El término '{term_clean}' ya está configurado")

    t = TwitterKeywordTerm(
        term=term_clean,
        term_type=data.term_type,
        is_active=True,
        created_by_id=user.id,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _term_dict(t)


@router.delete("/terms/{term_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_term(
    term_id: int,
    db:      Session = Depends(get_db),
    _:       User    = Depends(require_admin),
):
    """Elimina un término de búsqueda."""
    t = db.query(TwitterKeywordTerm).filter(TwitterKeywordTerm.id == term_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Término no encontrado")
    db.delete(t)
    db.commit()


@router.patch("/terms/{term_id}/toggle")
def toggle_term(
    term_id: int,
    db:      Session = Depends(get_db),
    _:       User    = Depends(require_admin),
):
    """Activa o desactiva un término sin eliminarlo."""
    t = db.query(TwitterKeywordTerm).filter(TwitterKeywordTerm.id == term_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Término no encontrado")
    t.is_active = not t.is_active
    db.commit()
    return _term_dict(t)


@router.post("/start")
def start_search(
    db:   Session = Depends(get_db),
    user: User    = Depends(require_admin),
):
    """Activa manualmente la búsqueda (is_active=True)."""
    terms = db.query(TwitterKeywordTerm).filter(TwitterKeywordTerm.is_active == True).count()
    if terms == 0:
        raise HTTPException(status_code=422, detail="Agrega al menos un término antes de activar la búsqueda")

    config = db.query(TwitterKeywordConfig).first()
    if not config:
        raise HTTPException(status_code=500, detail="Configuración no inicializada — contacta al administrador")

    config.is_active      = True
    config.activated_at   = datetime.now(timezone.utc)
    config.stopped_at     = None
    config.activated_by_id = user.id
    db.commit()
    return {"ok": True, "message": "Búsqueda activada"}


@router.post("/stop")
def stop_search(
    db: Session = Depends(get_db),
    _:  User    = Depends(require_admin),
):
    """Detiene la búsqueda (is_active=False)."""
    config = db.query(TwitterKeywordConfig).first()
    if not config:
        raise HTTPException(status_code=500, detail="Configuración no inicializada")

    config.is_active  = False
    config.stopped_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "message": "Búsqueda detenida"}


@router.post("/trigger")
def trigger_search(
    _: User = Depends(require_admin),
):
    """Dispara una ronda de búsqueda inmediatamente (sin esperar el cron)."""
    from app.workers.tasks.scraping import search_twitter_keywords
    task = search_twitter_keywords.delay()
    return {"ok": True, "task_id": task.id, "message": "Búsqueda iniciada — resultados en ~1 minuto"}
