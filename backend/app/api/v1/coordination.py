"""
Actividad coordinada — grupos de cuentas que publican el mismo texto (o casi) en una ventana corta.

El detector (workers/analytics/coordination.py) propone CANDIDATOS; aquí el equipo los revisa y los
marca confirmado/descartado. Esas decisiones son la referencia real para medir y calibrar el detector.
Acceso: analistas y administradores.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.api.audit_utils import log_action
from app.api.deps import require_analyst
from app.database import get_db
from app.models.bot import AccountProfile
from app.models.coordination import CoordinationCluster, CoordinationMember
from app.models.user import User

router = APIRouter(prefix="/coordination", tags=["Actividad coordinada"])

VALID_STATUS = ("nuevo", "confirmado", "descartado")


class ReviewBody(BaseModel):
    status: str
    note: Optional[str] = None


def _cluster_dict(c: CoordinationCluster) -> dict:
    return {
        "id": str(c.id),
        "kind": c.kind,
        "entity_id": str(c.entity_id) if c.entity_id else None,
        "entity_name": c.entity_name,
        "platform": c.platform,
        "first_seen": c.first_seen.isoformat(),
        "last_seen": c.last_seen.isoformat(),
        "accounts_count": c.accounts_count,
        "mentions_count": c.mentions_count,
        "span_hours": c.span_hours,
        "median_followers": c.median_followers,
        "low_follower_share": c.low_follower_share,
        "score": c.score,
        "sentiment_mix": c.sentiment_mix or {},
        "sample_text": c.sample_text,
        "status": c.status,
        "review_note": c.review_note,
        "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None,
        "reviewed_by_name": c.reviewer.full_name if c.reviewer else None,
        "detected_at": c.detected_at.isoformat() if c.detected_at else None,
    }


@router.get("/summary")
def summary(db: Session = Depends(get_db), _: User = Depends(require_analyst)):
    by_status = dict(db.query(CoordinationCluster.status, func.count()).group_by(CoordinationCluster.status).all())
    nuevo_alto = db.query(func.count(CoordinationCluster.id)).filter(
        CoordinationCluster.status == "nuevo", CoordinationCluster.score >= 0.6).scalar() or 0
    net_accounts = (
        db.query(func.count(distinct(CoordinationMember.author_ext_id)))
        .join(CoordinationCluster, CoordinationCluster.id == CoordinationMember.cluster_id)
        .filter(CoordinationCluster.kind == "red", CoordinationCluster.status != "descartado")
        .scalar() or 0
    )
    core = (
        db.query(func.count())
        .select_from(
            db.query(CoordinationMember.author_ext_id)
            .join(CoordinationCluster, CoordinationCluster.id == CoordinationMember.cluster_id)
            .filter(CoordinationCluster.kind == "red", CoordinationCluster.status != "descartado")
            .group_by(CoordinationMember.author_ext_id)
            .having(func.count(distinct(CoordinationMember.cluster_id)) >= 2)
            .subquery()
        )
        .scalar() or 0
    )
    conf, desc = by_status.get("confirmado", 0), by_status.get("descartado", 0)
    return {
        "nuevo": by_status.get("nuevo", 0), "confirmado": conf, "descartado": desc,
        "nuevo_alto_puntaje": nuevo_alto,
        "cuentas_en_redes": net_accounts,
        "cuentas_nucleo": core,                     # aparecen en >= 2 grupos
        "precision_revisada": round(conf / (conf + desc), 3) if (conf + desc) else None,
        "revisados": conf + desc,
    }


@router.get("/clusters")
def list_clusters(
    status: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    min_score: float = Query(0.0, ge=0, le=1),
    limit: int = Query(100, ge=1, le=300),
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst),
):
    q = db.query(CoordinationCluster).filter(CoordinationCluster.score >= min_score)
    if status:
        q = q.filter(CoordinationCluster.status == status)
    if kind:
        q = q.filter(CoordinationCluster.kind == kind)
    rows = q.order_by(CoordinationCluster.score.desc(), CoordinationCluster.first_seen.desc()).limit(limit).all()
    return [_cluster_dict(c) for c in rows]


@router.get("/clusters/{cluster_id}")
def get_cluster(cluster_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_analyst)):
    c = db.query(CoordinationCluster).filter(CoordinationCluster.id == cluster_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")

    # En cuántos grupos (de red) aparece cada cuenta: las que se repiten son el núcleo de la red
    authors = [m.author_ext_id for m in c.members if m.author_ext_id]
    recurrence = dict(
        db.query(CoordinationMember.author_ext_id, func.count(distinct(CoordinationMember.cluster_id)))
        .join(CoordinationCluster, CoordinationCluster.id == CoordinationMember.cluster_id)
        .filter(CoordinationMember.author_ext_id.in_(authors), CoordinationCluster.kind == "red")
        .group_by(CoordinationMember.author_ext_id).all()
    ) if authors else {}
    profile_ids = [m.account_profile_id for m in c.members if m.account_profile_id]
    bot_prob = dict(
        db.query(AccountProfile.id, AccountProfile.bot_probability).filter(AccountProfile.id.in_(profile_ids)).all()
    ) if profile_ids else {}

    return {
        **_cluster_dict(c),
        "members": [{
            "id": str(m.id),
            "username": m.author_username,
            "followers": m.followers,
            "account_created": m.account_created.isoformat() if m.account_created else None,
            "published_at": m.published_at.isoformat(),
            "sentiment": m.sentiment,
            "content": m.content_preview,
            "url": m.url,
            "network_clusters": recurrence.get(m.author_ext_id, 0),
            "bot_probability": float(bot_prob[m.account_profile_id]) if bot_prob.get(m.account_profile_id) is not None else None,
        } for m in c.members],
    }


@router.patch("/clusters/{cluster_id}/review")
def review_cluster(
    request: Request, cluster_id: uuid.UUID, body: ReviewBody,
    db: Session = Depends(get_db), user: User = Depends(require_analyst),
):
    if body.status not in VALID_STATUS:
        raise HTTPException(status_code=422, detail=f"Estado inválido. Opciones: {', '.join(VALID_STATUS)}")
    c = db.query(CoordinationCluster).filter(CoordinationCluster.id == cluster_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    c.status = body.status
    c.review_note = (body.note or "").strip() or None
    c.reviewed_by = user.id if body.status != "nuevo" else None
    c.reviewed_at = datetime.now(timezone.utc) if body.status != "nuevo" else None
    log_action(db, user.id, "coordination_review", request, "coordination_clusters", c.id, {"status": body.status})
    db.commit()
    db.refresh(c)
    return _cluster_dict(c)


@router.get("/accounts")
def recurring_accounts(
    min_clusters: int = Query(2, ge=1, le=20),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst),
):
    """Cuentas que aparecen en varios grupos de red (núcleo de la campaña), sin contar los descartados."""
    rows = (
        db.query(
            CoordinationMember.author_ext_id,
            func.max(CoordinationMember.author_username).label("username"),
            func.count(distinct(CoordinationMember.cluster_id)).label("clusters"),
            func.count(CoordinationMember.id).label("posts"),
            func.max(CoordinationMember.followers).label("followers"),
            func.max(CoordinationMember.account_created).label("created"),
            func.max(CoordinationMember.published_at).label("last_seen"),
        )
        .join(CoordinationCluster, CoordinationCluster.id == CoordinationMember.cluster_id)
        .filter(CoordinationCluster.kind == "red", CoordinationCluster.status != "descartado")
        .group_by(CoordinationMember.author_ext_id)
        .having(func.count(distinct(CoordinationMember.cluster_id)) >= min_clusters)
        .order_by(func.count(distinct(CoordinationMember.cluster_id)).desc(), func.count(CoordinationMember.id).desc())
        .limit(limit)
        .all()
    )
    return [{
        "author_ext_id": r.author_ext_id, "username": r.username, "clusters": r.clusters, "posts": r.posts,
        "followers": r.followers, "account_created": r.created.isoformat() if r.created else None,
        "last_seen": r.last_seen.isoformat() if r.last_seen else None,
    } for r in rows]
