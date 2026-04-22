from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.legal.domain.legal_case import LegalCase, LegalEvent, LegalDocument


class ILegalCaseRepository(ABC):
    @abstractmethod
    def list(self, level: str | None, status: str | None, entity_id: UUID | None) -> list[LegalCase]: ...

    @abstractmethod
    def get_by_id(self, case_id: UUID) -> LegalCase | None: ...

    @abstractmethod
    def create(self, case: LegalCase) -> LegalCase: ...

    @abstractmethod
    def update(self, case: LegalCase) -> LegalCase: ...


class ILegalEventRepository(ABC):
    @abstractmethod
    def list_by_case(self, case_id: UUID) -> list[LegalEvent]: ...

    @abstractmethod
    def create(self, event: LegalEvent) -> LegalEvent: ...


class ILegalDocumentRepository(ABC):
    @abstractmethod
    def list_by_case(self, case_id: UUID) -> list[LegalDocument]: ...

    @abstractmethod
    def create(self, doc: LegalDocument) -> LegalDocument: ...

    @abstractmethod
    def delete(self, doc_id: UUID) -> None: ...
