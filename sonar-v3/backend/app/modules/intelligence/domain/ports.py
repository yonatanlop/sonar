from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from app.modules.intelligence.domain.analysis import Anomaly, TrendForecast, DailySummary


class IAnomalyRepository(ABC):
    @abstractmethod
    def create(self, anomaly: Anomaly) -> Anomaly: ...

    @abstractmethod
    def list_by_entity(self, entity_id: UUID, limit: int = 20) -> list[Anomaly]: ...

    @abstractmethod
    def list_recent(self, hours: int = 24) -> list[Anomaly]: ...


class ITrendForecastRepository(ABC):
    @abstractmethod
    def create(self, forecast: TrendForecast) -> TrendForecast: ...

    @abstractmethod
    def list_by_entity(self, entity_id: UUID, from_date: date) -> list[TrendForecast]: ...

    @abstractmethod
    def delete_older_than(self, cutoff: date) -> int: ...


class IDailySummaryRepository(ABC):
    @abstractmethod
    def create(self, summary: DailySummary) -> DailySummary: ...

    @abstractmethod
    def get_by_entity_date(self, entity_id: UUID, summary_date: date) -> DailySummary | None: ...

    @abstractmethod
    def list_by_entity(self, entity_id: UUID, limit: int = 30) -> list[DailySummary]: ...
