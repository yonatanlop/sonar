from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.alerting.domain.alert import Alert, AlertRule
from app.modules.alerting.domain.ports import IAlertRuleRepository, IAlertRepository
from app.modules.alerting.infrastructure.orm import AlertRuleORM, AlertORM


class SqlAlertRuleRepository(IAlertRuleRepository):
    def __init__(self, db: Session):
        self._db = db

    def list(self, entity_id: UUID | None = None) -> list[AlertRule]:
        q = self._db.query(AlertRuleORM)
        if entity_id:
            q = q.filter(AlertRuleORM.entity_id == str(entity_id))
        return [r.to_domain() for r in q.order_by(AlertRuleORM.created_at.desc()).all()]

    def get_by_id(self, rule_id: UUID) -> AlertRule | None:
        row = self._db.query(AlertRuleORM).filter(AlertRuleORM.id == str(rule_id)).first()
        return row.to_domain() if row else None

    def get_active(self) -> list[AlertRule]:
        rows = self._db.query(AlertRuleORM).filter(AlertRuleORM.active == True).all()
        return [r.to_domain() for r in rows]

    def create(self, rule: AlertRule) -> AlertRule:
        row = AlertRuleORM(
            id=str(rule.id), entity_id=str(rule.entity_id) if rule.entity_id else None,
            name=rule.name, rule_type=rule.rule_type, threshold=rule.threshold,
            window_minutes=rule.window_minutes, severity=rule.severity,
            active=rule.active, notify_users=rule.notify_users,
            created_by=str(rule.created_by), created_at=rule.created_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def toggle(self, rule_id: UUID) -> AlertRule:
        row = self._db.query(AlertRuleORM).filter(AlertRuleORM.id == str(rule_id)).first()
        row.active = not row.active
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def delete(self, rule_id: UUID) -> None:
        self._db.query(AlertRuleORM).filter(AlertRuleORM.id == str(rule_id)).delete()
        self._db.commit()


class SqlAlertRepository(IAlertRepository):
    def __init__(self, db: Session):
        self._db = db

    def list(self, entity_id: UUID | None = None, unread_only: bool = False,
             limit: int = 50) -> list[Alert]:
        q = self._db.query(AlertORM)
        if entity_id:
            q = q.filter(AlertORM.entity_id == str(entity_id))
        if unread_only:
            q = q.filter(AlertORM.acknowledged == False)
        rows = q.order_by(AlertORM.triggered_at.desc()).limit(limit).all()
        return [r.to_domain() for r in rows]

    def get_by_id(self, alert_id: UUID) -> Alert | None:
        row = self._db.query(AlertORM).filter(AlertORM.id == str(alert_id)).first()
        return row.to_domain() if row else None

    def count_unread(self, user_id: UUID) -> int:
        return self._db.query(AlertORM).filter(AlertORM.acknowledged == False).count()

    def create(self, alert: Alert) -> Alert:
        row = AlertORM(
            id=str(alert.id), rule_id=str(alert.rule_id), entity_id=str(alert.entity_id),
            triggered_at=alert.triggered_at, message=alert.message, severity=alert.severity,
            acknowledged=False, anomaly_id=str(alert.anomaly_id) if alert.anomaly_id else None,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def acknowledge(self, alert_id: UUID, user_id: UUID, action: str, notes: str) -> Alert:
        row = self._db.query(AlertORM).filter(AlertORM.id == str(alert_id)).first()
        row.acknowledged = True
        row.acknowledged_by = str(user_id)
        row.acknowledged_at = datetime.now(timezone.utc)
        row.action_taken = action
        row.action_notes = notes
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()
