from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.monitoring.domain.entity import Entity, EntityAlias, Keyword, TwitterFeed, SocialPlatform
from app.modules.monitoring.domain.ports import (
    IEntityRepository, IEntityAliasRepository, IKeywordRepository,
    ITwitterFeedRepository, ISocialPlatformRepository
)
from app.modules.monitoring.infrastructure.orm import (
    EntityORM, EntityAliasORM, KeywordORM, TwitterFeedORM, SocialPlatformORM
)


class SqlEntityRepository(IEntityRepository):
    def __init__(self, db: Session):
        self._db = db

    def get_by_id(self, entity_id: UUID) -> Entity | None:
        row = self._db.query(EntityORM).filter(EntityORM.id == str(entity_id)).first()
        return row.to_domain() if row else None

    def list(self, active_only: bool = True) -> list[Entity]:
        q = self._db.query(EntityORM)
        if active_only:
            q = q.filter(EntityORM.active == True)
        return [r.to_domain() for r in q.order_by(EntityORM.name).all()]

    def create(self, entity: Entity) -> Entity:
        row = EntityORM.from_domain(entity)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def update(self, entity: Entity) -> Entity:
        row = self._db.query(EntityORM).filter(EntityORM.id == str(entity.id)).first()
        if not row:
            return entity
        row.name = entity.name
        row.active = entity.active
        row.description = entity.description
        row.photo_url = entity.photo_url
        row.monitoring_type = entity.monitoring_type
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def delete(self, entity_id: UUID) -> None:
        self._db.query(EntityORM).filter(EntityORM.id == str(entity_id)).delete()
        self._db.commit()


class SqlEntityAliasRepository(IEntityAliasRepository):
    def __init__(self, db: Session):
        self._db = db

    def list_by_entity(self, entity_id: UUID) -> list[EntityAlias]:
        rows = self._db.query(EntityAliasORM).filter(EntityAliasORM.entity_id == str(entity_id)).all()
        return [r.to_domain() for r in rows]

    def create(self, alias: EntityAlias) -> EntityAlias:
        row = EntityAliasORM(
            id=str(alias.id), entity_id=str(alias.entity_id),
            alias=alias.alias, created_by=str(alias.created_by),
            created_at=alias.created_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def delete(self, alias_id: UUID) -> None:
        self._db.query(EntityAliasORM).filter(EntityAliasORM.id == str(alias_id)).delete()
        self._db.commit()


class SqlKeywordRepository(IKeywordRepository):
    def __init__(self, db: Session):
        self._db = db

    def list_by_entity(self, entity_id: UUID) -> list[Keyword]:
        rows = self._db.query(KeywordORM).filter(KeywordORM.entity_id == str(entity_id)).all()
        return [r.to_domain() for r in rows]

    def list_active(self) -> list[Keyword]:
        rows = self._db.query(KeywordORM).filter(KeywordORM.active == True).all()
        return [r.to_domain() for r in rows]

    def create(self, keyword: Keyword) -> Keyword:
        row = KeywordORM(
            id=str(keyword.id), entity_id=str(keyword.entity_id),
            keyword=keyword.keyword, language=keyword.language,
            weight=keyword.weight, active=keyword.active,
            created_by=str(keyword.created_by), created_at=keyword.created_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def delete(self, keyword_id: UUID) -> None:
        self._db.query(KeywordORM).filter(KeywordORM.id == str(keyword_id)).delete()
        self._db.commit()


class SqlTwitterFeedRepository(ITwitterFeedRepository):
    def __init__(self, db: Session):
        self._db = db

    def list(self, active_only: bool = False) -> list[TwitterFeed]:
        q = self._db.query(TwitterFeedORM)
        if active_only:
            q = q.filter(TwitterFeedORM.active == True)
        return [r.to_domain() for r in q.order_by(TwitterFeedORM.display_name).all()]

    def get_by_id(self, feed_id: UUID) -> TwitterFeed | None:
        row = self._db.query(TwitterFeedORM).filter(TwitterFeedORM.id == str(feed_id)).first()
        return row.to_domain() if row else None

    def create(self, feed: TwitterFeed) -> TwitterFeed:
        row = TwitterFeedORM(
            id=str(feed.id), feed_type=feed.feed_type, term=feed.term,
            display_name=feed.display_name, entity_id=str(feed.entity_id) if feed.entity_id else None,
            active=feed.active, created_by=str(feed.created_by), created_at=feed.created_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def toggle(self, feed_id: UUID) -> TwitterFeed:
        row = self._db.query(TwitterFeedORM).filter(TwitterFeedORM.id == str(feed_id)).first()
        row.active = not row.active
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def delete(self, feed_id: UUID) -> None:
        self._db.query(TwitterFeedORM).filter(TwitterFeedORM.id == str(feed_id)).delete()
        self._db.commit()


class SqlSocialPlatformRepository(ISocialPlatformRepository):
    def __init__(self, db: Session):
        self._db = db

    def list(self) -> list[SocialPlatform]:
        return [r.to_domain() for r in self._db.query(SocialPlatformORM).all()]

    def get_by_code(self, code: str) -> SocialPlatform | None:
        row = self._db.query(SocialPlatformORM).filter(SocialPlatformORM.code == code).first()
        return row.to_domain() if row else None

    def update_status(self, platform_id: int, active: bool) -> SocialPlatform:
        row = self._db.query(SocialPlatformORM).filter(SocialPlatformORM.id == platform_id).first()
        row.active = active
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()
