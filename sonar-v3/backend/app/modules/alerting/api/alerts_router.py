from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.shared.deps import get_db, get_current_user, require_analyst
from app.shared.redis_client import redis_client
from app.modules.alerting.infrastructure.alert_repository import (
    SqlAlertRuleRepository, SqlAlertRepository
)

router = APIRouter(prefix="/alerts", tags=["Alertas"])

VALID_ACTIONS = {"reported_platform", "escalated_mira", "escalated_church", "opportunity", "dismissed"}


# ── Schemas ──────────────────────────────────────────────────
class AlertRuleCreate(BaseModel):
    entity_id: UUID | None = None
    name: str
    rule_type: str
    threshold: int
    window_minutes: int = 60
    severity: str = "medium"
    notify_users: list[str] = []


class AlertAcknowledgeIn(BaseModel):
    action: str
    notes: str = ""


class AlertRuleOut(BaseModel):
    id: UUID
    entity_id: UUID | None = None
    name: str
    rule_type: str
    threshold: int
    window_minutes: int
    severity: str
    active: bool
    notify_users: list


class AlertOut(BaseModel):
    id: UUID
    rule_id: UUID
    entity_id: UUID
    triggered_at: datetime
    message: str
    severity: str
    acknowledged: bool
    acknowledged_by: UUID | None = None
    acknowledged_at: datetime | None = None
    action_taken: str | None = None
    action_notes: str | None = None


# ── Rules ─────────────────────────────────────────────────────
@router.get("/rules", response_model=list[AlertRuleOut])
def list_rules(
    entity_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    repo = SqlAlertRuleRepository(db)
    return [_rule_out(r) for r in repo.list(entity_id=entity_id)]


@router.post("/rules", response_model=AlertRuleOut, status_code=201)
def create_rule(
    data: AlertRuleCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_analyst),
):
    from app.modules.alerting.domain.alert import AlertRule
    repo = SqlAlertRuleRepository(db)
    rule = AlertRule(
        id=uuid4(), entity_id=data.entity_id, name=data.name,
        rule_type=data.rule_type, threshold=data.threshold,
        window_minutes=data.window_minutes, severity=data.severity,
        active=True, notify_users=data.notify_users,
        created_by=current_user.id, created_at=datetime.now(timezone.utc),
    )
    return _rule_out(repo.create(rule))


@router.patch("/rules/{rule_id}", response_model=AlertRuleOut)
def toggle_rule(rule_id: UUID, db: Session = Depends(get_db), _=Depends(require_analyst)):
    repo = SqlAlertRuleRepository(db)
    return _rule_out(repo.toggle(rule_id))


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: UUID, db: Session = Depends(get_db), _=Depends(require_analyst)):
    SqlAlertRuleRepository(db).delete(rule_id)


# ── Alerts ────────────────────────────────────────────────────
@router.get("", response_model=list[AlertOut])
def list_alerts(
    entity_id: UUID | None = Query(None),
    unread_only: bool = Query(False),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    repo = SqlAlertRepository(db)
    return [_alert_out(a) for a in repo.list(entity_id=entity_id, unread_only=unread_only, limit=limit)]


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return {"count": SqlAlertRepository(db).count_unread(current_user.id)}


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(
    alert_id: UUID,
    data: AlertAcknowledgeIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.shared.exceptions import NotFoundError
    if data.action not in VALID_ACTIONS:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=f"Acción inválida. Opciones: {VALID_ACTIONS}")
    repo = SqlAlertRepository(db)
    alert = repo.get_by_id(alert_id)
    if not alert:
        raise NotFoundError("Alerta no encontrada")
    return _alert_out(repo.acknowledge(alert_id, current_user.id, data.action, data.notes))


# ── SSE stream ────────────────────────────────────────────────
@router.get("/stream")
async def alert_stream(current_user=Depends(get_current_user)):
    async def event_generator():
        user_key = f"alerts:{current_user.id}"
        global_key = "alerts:global"
        while True:
            msg = redis_client.lpop(user_key) or redis_client.lpop(global_key)
            if msg:
                yield f"data: {msg}\n\n"
            await asyncio.sleep(2)
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Helpers ───────────────────────────────────────────────────
def _rule_out(r) -> AlertRuleOut:
    return AlertRuleOut(
        id=r.id, entity_id=r.entity_id, name=r.name, rule_type=r.rule_type,
        threshold=r.threshold, window_minutes=r.window_minutes,
        severity=r.severity, active=r.active, notify_users=r.notify_users,
    )


def _alert_out(a) -> AlertOut:
    return AlertOut(
        id=a.id, rule_id=a.rule_id, entity_id=a.entity_id,
        triggered_at=a.triggered_at, message=a.message, severity=a.severity,
        acknowledged=a.acknowledged, acknowledged_by=a.acknowledged_by,
        acknowledged_at=a.acknowledged_at, action_taken=a.action_taken,
        action_notes=a.action_notes,
    )
