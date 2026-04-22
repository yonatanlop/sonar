from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class AlertRule:
    id: UUID
    entity_id: UUID | None
    name: str
    rule_type: str
    threshold: int
    window_minutes: int
    severity: str
    active: bool
    notify_users: list
    created_by: UUID
    created_at: datetime


@dataclass
class Alert:
    id: UUID
    rule_id: UUID
    entity_id: UUID
    triggered_at: datetime
    message: str
    severity: str
    acknowledged: bool
    acknowledged_by: UUID | None
    acknowledged_at: datetime | None
    action_taken: str | None
    action_notes: str | None
    anomaly_id: UUID | None
