import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user, require_analyst
from app.core.security import decode_token, is_token_blacklisted
from app.database import SessionLocal, get_db
from app.models.alert import Alert, AlertRule
from app.models.entity import Entity
from app.models.mention import Mention
from app.models.user import User

router = APIRouter(prefix="/alerts", tags=["Alertas"])

PAGE_SIZE = 20


# ── Schemas ───────────────────────────────────────────────────

class AlertRuleCreate(BaseModel):
    entity_id:      Optional[uuid.UUID] = None
    name:           str
    rule_type:      str
    threshold:      int
    window_minutes: int = 60
    severity:       str = "medium"
    notify_users:   list[str] = []


class AlertAcknowledgeIn(BaseModel):
    action: str   # reported_platform | escalated_mira | escalated_church | opportunity | dismissed
    notes:  str = ""


# ── Helpers ───────────────────────────────────────────────────

def _alert_dict(a: Alert, db: Session) -> dict:
    entity = db.query(Entity).filter(Entity.id == a.entity_id).first()
    ack_user = None
    if a.acknowledged_by:
        u = db.query(User).filter(User.id == a.acknowledged_by).first()
        ack_user = u.full_name if u else None

    # v2: contexto IA si la alerta viene de una anomalía
    context_explanation = None
    if a.anomaly_id:
        from app.models.anomaly import Anomaly
        anomaly = db.query(Anomaly).filter(Anomaly.id == a.anomaly_id).first()
        if anomaly:
            context_explanation = anomaly.context_explanation

    return {
        "id":                   str(a.id),
        "rule_id":              str(a.rule_id),
        "entity_id":            str(a.entity_id),
        "entity_name":          entity.name if entity else "—",
        "rule_type":            a.rule.rule_type if a.rule else None,
        "message":              a.message,
        "severity":             a.severity,
        "acknowledged":         a.acknowledged,
        "acknowledged_by_name": ack_user,
        "acknowledged_at":      a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        "action_taken":         a.action_taken,
        "action_notes":         a.action_notes,
        "triggered_at":         a.triggered_at.isoformat(),
        "context_explanation":  context_explanation,
    }


def _rule_dict(r: AlertRule) -> dict:
    return {
        "id":             str(r.id),
        "entity_id":      str(r.entity_id) if r.entity_id else None,
        "name":           r.name,
        "rule_type":      r.rule_type,
        "threshold":      r.threshold,
        "window_minutes": r.window_minutes,
        "severity":       r.severity,
        "active":         r.active,
        "notify_users":   r.notify_users or [],
        "created_at":     r.created_at.isoformat(),
    }


# ── SSE: stream de alertas en tiempo real ─────────────────────

@router.get("/stream")
async def alert_stream(request: Request, token: str = Query(...)):
    """Server-Sent Events — entrega alertas en tiempo real al frontend."""
    if is_token_blacklisted(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    import redis as redis_lib
    from app.core.config import settings
    r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

    async def generator():
        while True:
            if await request.is_disconnected():
                break
            # lpop es O(1) y no bloquea el event loop
            raw = r.lpop(f"alerts:{user_id}")
            if raw:
                yield {"event": "new_alert", "data": raw}
            await asyncio.sleep(4)

    return EventSourceResponse(generator())


# ── Alertas ───────────────────────────────────────────────────

@router.get("")
def list_alerts(
    severity:     Optional[str]       = Query(None),
    entity_id:    Optional[uuid.UUID] = Query(None),
    acknowledged: Optional[str]       = Query(None),   # "true" | "false"
    page:         int                 = Query(1, ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(Alert)

    if severity:
        query = query.filter(Alert.severity == severity)
    if entity_id:
        query = query.filter(Alert.entity_id == entity_id)
    if acknowledged == "true":
        query = query.filter(Alert.acknowledged == True)
    elif acknowledged == "false":
        query = query.filter(Alert.acknowledged == False)

    total = query.count()
    items = (query
             .order_by(Alert.triggered_at.desc())
             .offset((page - 1) * PAGE_SIZE)
             .limit(PAGE_SIZE)
             .all())

    return {
        "total": total,
        "page":  page,
        "pages": (total + PAGE_SIZE - 1) // PAGE_SIZE,
        "items": [_alert_dict(a, db) for a in items],
    }


VALID_ACTIONS = {"reported_platform", "escalated_mira", "escalated_church", "opportunity", "dismissed"}


@router.post("/{alert_id}/acknowledge", status_code=status.HTTP_200_OK)
def acknowledge_alert(
    alert_id: uuid.UUID,
    body: AlertAcknowledgeIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    if alert.acknowledged:
        raise HTTPException(status_code=400, detail="La alerta ya fue atendida")
    if body.action not in VALID_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Acción inválida: {body.action}")

    alert.acknowledged    = True
    alert.acknowledged_by = current_user.id
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.action_taken    = body.action
    alert.action_notes    = body.notes or None
    db.commit()
    return _alert_dict(alert, db)


# ── Reglas de alerta ──────────────────────────────────────────

VALID_RULE_TYPES = {"volume_spike", "negative_threshold", "bot_activity",
                    "keyword_critical", "campaign_detected", "hate_speech",
                    "anomaly_detected", "negative_mention"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}


@router.get("/rules")
def list_rules(
    entity_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(AlertRule)
    if entity_id:
        query = query.filter(AlertRule.entity_id == entity_id)
    return [_rule_dict(r) for r in query.order_by(AlertRule.created_at.desc()).all()]


@router.post("/rules", status_code=status.HTTP_201_CREATED)
def create_rule(
    data: AlertRuleCreate,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_db),
):
    if data.rule_type not in VALID_RULE_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipo de regla inválido: {data.rule_type}")
    if data.severity not in VALID_SEVERITIES:
        raise HTTPException(status_code=400, detail=f"Severidad inválida: {data.severity}")

    rule = AlertRule(**data.model_dump(), created_by=current_user.id)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule_dict(rule)


@router.patch("/rules/{rule_id}")
def toggle_rule(
    rule_id: uuid.UUID,
    _=Depends(require_analyst),
    db: Session = Depends(get_db),
):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    rule.active = not rule.active
    db.commit()
    return _rule_dict(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: uuid.UUID,
    _=Depends(require_analyst),
    db: Session = Depends(get_db),
):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    db.delete(rule)
    db.commit()


# ── Bandeja de menciones negativas ────────────────────────────

@router.get("/inbox/count")
def get_inbox_count(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Contador de alertas negative_mention pendientes (para badge del sidebar)."""
    count = (
        db.query(func.count(Alert.id))
        .join(AlertRule, Alert.rule_id == AlertRule.id)
        .filter(
            AlertRule.rule_type == "negative_mention",
            Alert.acknowledged  == False,
        )
        .scalar()
    )
    return {"count": count or 0}


@router.get("/inbox")
def get_inbox(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Alertas de tipo negative_mention no atendidas, con datos completos
    de la mención asociada. Accesible a todos los roles.
    """
    rows = (
        db.query(Alert)
        .join(AlertRule, Alert.rule_id == AlertRule.id)
        .filter(
            AlertRule.rule_type == "negative_mention",
            Alert.acknowledged  == False,
        )
        .order_by(Alert.triggered_at.desc())
        .limit(100)
        .all()
    )

    result = []
    for a in rows:
        entity = db.query(Entity).filter(Entity.id == a.entity_id).first()
        m = db.query(Mention).filter(Mention.id == a.mention_id).first() if a.mention_id else None
        result.append({
            "id":           str(a.id),
            "entity_id":    str(a.entity_id),
            "entity_name":  entity.name if entity else "—",
            "severity":     a.severity,
            "message":      a.message,
            "triggered_at": a.triggered_at.isoformat(),
            "mention": {
                "id":              str(m.id),
                "content":         m.content,
                "platform_code":   m.platform_code,
                "author_username": m.author_username,
                "sentiment_label": m.sentiment_label,
                "sentiment_score": float(m.sentiment_score or 0),
                "urgency_score":   m.urgency_score,
                "is_hate_speech":  m.is_hate_speech,
                "url":             m.url,
                "collected_at":    m.collected_at.isoformat(),
            } if m else None,
        })
    return result
