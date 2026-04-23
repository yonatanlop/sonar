from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database import Base
from app.modules.alerting.domain.alert import Alert, AlertRule


class AlertRuleORM(Base):
    __tablename__ = "alert_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("entities.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    rule_type: Mapped[str] = mapped_column(
        Enum("volume_spike", "negative_threshold", "bot_activity",
             "keyword_critical", "campaign_detected", "hate_speech", "anomaly_detected",
             name="alert_rule_type"),
        nullable=False,
    )
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    severity: Mapped[str] = mapped_column(
        Enum("low", "medium", "high", "critical", name="alert_severity"),
        nullable=False, default="medium",
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_users: Mapped[list] = mapped_column(JSONB, default=list, server_default='[]')
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    alerts: Mapped[list["AlertORM"]] = relationship("AlertORM", back_populates="rule")

    def to_domain(self) -> AlertRule:
        return AlertRule(
            id=self.id, entity_id=self.entity_id, name=self.name,
            rule_type=self.rule_type, threshold=self.threshold,
            window_minutes=self.window_minutes, severity=self.severity,
            active=self.active, notify_users=self.notify_users or [],
            created_by=self.created_by, created_at=self.created_at,
        )


class AlertORM(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("alert_rules.id"), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(
        Enum("low", "medium", "high", "critical", name="alert_severity_val"),
        nullable=False,
    )
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    action_taken: Mapped[str | None] = mapped_column(String(30), nullable=True)
    action_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    anomaly_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("anomalies.id", ondelete="SET NULL"), nullable=True
    )

    rule: Mapped["AlertRuleORM"] = relationship("AlertRuleORM", back_populates="alerts")

    def to_domain(self) -> Alert:
        return Alert(
            id=self.id, rule_id=self.rule_id, entity_id=self.entity_id,
            triggered_at=self.triggered_at, message=self.message,
            severity=self.severity, acknowledged=self.acknowledged,
            acknowledged_by=self.acknowledged_by, acknowledged_at=self.acknowledged_at,
            action_taken=self.action_taken, action_notes=self.action_notes,
            anomaly_id=self.anomaly_id,
        )
