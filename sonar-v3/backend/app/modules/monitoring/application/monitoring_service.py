from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.modules.monitoring.domain.entity import (
    Entity, EntityAlias, Keyword, TwitterFeed
)
from app.modules.monitoring.domain.ports import (
    IEntityRepository, IEntityAliasRepository, IKeywordRepository,
    ITwitterFeedRepository, ISocialPlatformRepository
)
from app.modules.monitoring.application.schemas import (
    EntityCreate, EntityPatch, AliasCreate, KeywordCreate, TwitterFeedCreate
)
from app.shared.exceptions import NotFoundError, ConflictError


class EntityService:
    def __init__(self, repo: IEntityRepository, alias_repo: IEntityAliasRepository,
                 kw_repo: IKeywordRepository):
        self._repo = repo
        self._alias_repo = alias_repo
        self._kw_repo = kw_repo

    def list(self, active_only: bool = True) -> list[Entity]:
        return self._repo.list(active_only=active_only)

    def get(self, entity_id: UUID) -> Entity:
        e = self._repo.get_by_id(entity_id)
        if not e:
            raise NotFoundError("Entidad no encontrada")
        return e

    def create(self, data: EntityCreate, created_by: UUID) -> Entity:
        entity = Entity(
            id=uuid4(),
            name=data.name,
            entity_type_id=data.entity_type_id,
            country_code=data.country_code,
            description=data.description,
            photo_url=data.photo_url,
            active=True,
            monitoring_type=data.monitoring_type,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
        )
        return self._repo.create(entity)

    def update(self, entity_id: UUID, data: EntityPatch) -> Entity:
        entity = self.get(entity_id)
        if data.name is not None:
            entity.name = data.name
        if data.active is not None:
            entity.active = data.active
        if data.description is not None:
            entity.description = data.description
        if data.photo_url is not None:
            entity.photo_url = data.photo_url
        if data.monitoring_type is not None:
            entity.monitoring_type = data.monitoring_type
        return self._repo.update(entity)

    def delete(self, entity_id: UUID) -> None:
        self.get(entity_id)
        self._repo.delete(entity_id)

    def add_alias(self, entity_id: UUID, data: AliasCreate, created_by: UUID) -> EntityAlias:
        self.get(entity_id)
        alias = EntityAlias(
            id=uuid4(),
            entity_id=entity_id,
            alias=data.alias,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
        )
        return self._alias_repo.create(alias)

    def delete_alias(self, alias_id: UUID) -> None:
        self._alias_repo.delete(alias_id)

    def add_keyword(self, entity_id: UUID, data: KeywordCreate, created_by: UUID) -> Keyword:
        self.get(entity_id)
        kw = Keyword(
            id=uuid4(),
            entity_id=entity_id,
            keyword=data.keyword,
            language=data.language,
            weight=data.weight,
            active=True,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
        )
        return self._kw_repo.create(kw)

    def delete_keyword(self, keyword_id: UUID) -> None:
        self._kw_repo.delete(keyword_id)


class TwitterFeedService:
    def __init__(self, repo: ITwitterFeedRepository, entity_repo: IEntityRepository):
        self._repo = repo
        self._entity_repo = entity_repo

    def list(self) -> list[TwitterFeed]:
        return self._repo.list()

    def create(self, data: TwitterFeedCreate, created_by: UUID) -> TwitterFeed:
        display_map = {
            "user": f"@{data.term}",
            "hashtag": f"#{data.term}",
            "keyword": data.term,
        }
        feed = TwitterFeed(
            id=uuid4(),
            feed_type=data.feed_type,
            term=data.term,
            display_name=display_map.get(data.feed_type, data.term),
            entity_id=None,
            active=True,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
        )
        return self._repo.create(feed)

    def toggle(self, feed_id: UUID) -> TwitterFeed:
        feed = self._repo.get_by_id(feed_id)
        if not feed:
            raise NotFoundError("Feed no encontrado")
        return self._repo.toggle(feed_id)

    def delete(self, feed_id: UUID) -> None:
        feed = self._repo.get_by_id(feed_id)
        if not feed:
            raise NotFoundError("Feed no encontrado")
        self._repo.delete(feed_id)
