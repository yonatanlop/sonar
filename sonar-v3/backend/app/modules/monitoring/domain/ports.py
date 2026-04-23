from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.monitoring.domain.entity import (
    Entity, EntityAlias, EntityType, Keyword, TwitterFeed, SocialPlatform, Country
)


class IEntityRepository(ABC):
    @abstractmethod
    def get_by_id(self, entity_id: UUID) -> Entity | None: ...

    @abstractmethod
    def list(self, active_only: bool = True) -> list[Entity]: ...

    @abstractmethod
    def create(self, entity: Entity) -> Entity: ...

    @abstractmethod
    def update(self, entity: Entity) -> Entity: ...

    @abstractmethod
    def delete(self, entity_id: UUID) -> None: ...


class IEntityAliasRepository(ABC):
    @abstractmethod
    def list_by_entity(self, entity_id: UUID) -> list[EntityAlias]: ...

    @abstractmethod
    def create(self, alias: EntityAlias) -> EntityAlias: ...

    @abstractmethod
    def delete(self, alias_id: UUID) -> None: ...


class IKeywordRepository(ABC):
    @abstractmethod
    def list_by_entity(self, entity_id: UUID) -> list[Keyword]: ...

    @abstractmethod
    def list_active(self) -> list[Keyword]: ...

    @abstractmethod
    def create(self, keyword: Keyword) -> Keyword: ...

    @abstractmethod
    def delete(self, keyword_id: UUID) -> None: ...


class ITwitterFeedRepository(ABC):
    @abstractmethod
    def list(self, active_only: bool = False) -> list[TwitterFeed]: ...

    @abstractmethod
    def get_by_id(self, feed_id: UUID) -> TwitterFeed | None: ...

    @abstractmethod
    def create(self, feed: TwitterFeed) -> TwitterFeed: ...

    @abstractmethod
    def toggle(self, feed_id: UUID) -> TwitterFeed: ...

    @abstractmethod
    def delete(self, feed_id: UUID) -> None: ...


class ISocialPlatformRepository(ABC):
    @abstractmethod
    def list(self) -> list[SocialPlatform]: ...

    @abstractmethod
    def get_by_code(self, code: str) -> SocialPlatform | None: ...

    @abstractmethod
    def update_status(self, platform_id: int, active: bool) -> SocialPlatform: ...


class IEntityQueryService(ABC):
    """Consumed by other modules to look up entity data without importing monitoring ORM."""

    @abstractmethod
    def get_name(self, entity_id: UUID) -> str | None: ...

    @abstractmethod
    def get_active_keywords(self) -> list[dict]: ...
