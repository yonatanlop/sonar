from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.identity.domain.user import User


class IUserRepository(ABC):
    @abstractmethod
    def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    def get_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    def list_active(self) -> list[User]: ...

    @abstractmethod
    def list_all(self) -> list[User]: ...

    @abstractmethod
    def create(self, user: User) -> User: ...

    @abstractmethod
    def update(self, user: User) -> User: ...

    @abstractmethod
    def delete(self, user_id: UUID) -> None: ...
