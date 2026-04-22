from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.reporting.domain.report import Report


class IReportRepository(ABC):
    @abstractmethod
    def list(self, created_by: UUID | None = None) -> list[Report]: ...

    @abstractmethod
    def get_by_id(self, report_id: UUID) -> Report | None: ...

    @abstractmethod
    def create(self, report: Report) -> Report: ...

    @abstractmethod
    def update_path(self, report_id: UUID, file_path: str) -> Report: ...

    @abstractmethod
    def delete(self, report_id: UUID) -> None: ...
