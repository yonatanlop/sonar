from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.actor_map.domain.actor import Actor, ActorRelation, ActorGroup


class IActorRepository(ABC):
    @abstractmethod
    def list(self, active_only: bool = True) -> list[Actor]: ...

    @abstractmethod
    def get_by_id(self, actor_id: UUID) -> Actor | None: ...

    @abstractmethod
    def create(self, actor: Actor) -> Actor: ...

    @abstractmethod
    def update(self, actor: Actor) -> Actor: ...


class IActorRelationRepository(ABC):
    @abstractmethod
    def list_all(self) -> list[ActorRelation]: ...

    @abstractmethod
    def create(self, relation: ActorRelation) -> ActorRelation: ...

    @abstractmethod
    def delete(self, relation_id: UUID) -> None: ...


class IActorGroupRepository(ABC):
    @abstractmethod
    def list(self) -> list[ActorGroup]: ...

    @abstractmethod
    def create(self, group: ActorGroup) -> ActorGroup: ...
