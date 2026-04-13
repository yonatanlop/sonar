import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user, require_analyst
from app.core.security import decode_token
from app.database import SessionLocal, get_db
from app.models.alert import Alert, AlertRule
from app.models.entity import Entity
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
        "triggered_at":         a.triggered_at.isoformat(),
        "context_explanation":  context_explanation,   # v2: explicación IA (solo en anomalías)
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
        "created_at":     r.created_at.isoformat(),
    }


# ── SSE: stream de alertas en tiempo real ─────────────────────

@router.get("/stream")
async def alert_stream(request: Request, token: str = Query(...)):
    """Server-Sent Events — entrega alertas en tiempo real al frontend."""
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


@router.post("/{alert_id}/acknowledge", status_code=status.HTTP_200_OK)
def acknowledge_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    if alert.acknowledged:
        raise HTTPException(status_code=400, detail="La alerta ya fue atendida")

    alert.acknowledged    = True
    alert.acknowledged_by = current_user.id
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    return _alert_dict(alert, db)


# ── Reglas de alerta ──────────────────────────────────────────

VALID_RULE_TYPES = {"volume_spike", "negative_threshold", "bot_activity",
                    "keyword_critical", "campaign_detected", "hate_speech",
                    "anomaly_detected"}
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
