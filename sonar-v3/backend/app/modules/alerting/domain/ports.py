from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.alerting.domain.alert import Alert, AlertRule


class IAlertRuleRepository(ABC):
    @abstractmethod
    def list(self, entity_id: UUID | None = None) -> list[AlertRule]: ...

    @abstractmethod
    def get_by_id(self, rule_id: UUID) -> AlertRule | None: ...

    @abstractmethod
    def get_active(self) -> list[AlertRule]: ...

    @abstractmethod
    def create(self, rule: AlertRule) -> AlertRule: ...

    @abstractmethod
    def toggle(self, rule_id: UUID) -> AlertRule: ...

    @abstractmethod
    def delete(self, rule_id: UUID) -> None: ...


class IAlertRepository(ABC):
    @abstractmethod
    def list(self, entity_id: UUID | None = None, unread_only: bool = False,
             limit: int = 50) -> list[Alert]: ...

    @abstractmethod
    def get_by_id(self, alert_id: UUID) -> Alert | None: ...

    @abstractmethod
    def count_unread(self, user_id: UUID) -> int: ...

    @abstractmethod
    def create(self, alert: Alert) -> Alert: ...

    @abstractmethod
    def acknowledge(self, alert_id: UUID, user_id: UUID,
                    action: str, notes: str) -> Alert: ...
