from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database import Base
from app.modules.monitoring.domain.entity import (
    Entity, EntityAlias, EntityType, Keyword, TwitterFeed, SocialPlatform, Country
)


class CountryORM(Base):
    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    def to_domain(self) -> Country:
        return Country(code=self.code, name=self.name)


class EntityTypeORM(Base):
    __tablename__ = "entity_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    entities: Mapped[list["EntityORM"]] = relationship("EntityORM", back_populates="entity_type")

    def to_domain(self) -> EntityType:
        return EntityType(id=self.id, name=self.name)


class EntityAliasORM(Base):
    __tablename__ = "entity_aliases"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    entity_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("entities.id"), nullable=False)
    alias: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    entity: Mapped["EntityORM"] = relationship("EntityORM", back_populates="aliases")

    def to_domain(self) -> EntityAlias:
        return EntityAlias(
            id=self.id, entity_id=self.entity_id, alias=self.alias,
            created_by=self.created_by, created_at=self.created_at,
        )


class KeywordORM(Base):
    __tablename__ = "keywords"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    entity_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("entities.id"), nullable=False)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    language: Mapped[str] = mapped_column(String(2), nullable=False, default="es")
    weight: Mapped[int] = mapped_column(SmallInteger, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    entity: Mapped["EntityORM"] = relationship("EntityORM", back_populates="keywords")

    def to_domain(self) -> Keyword:
        return Keyword(
            id=self.id, entity_id=self.entity_id, keyword=self.keyword,
            language=self.language, weight=self.weight, active=self.active,
            created_by=self.created_by, created_at=self.created_at,
        )


class EntityORM(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("entity_types.id"), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2), ForeignKey("countries.code"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    monitoring_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    entity_type: Mapped["EntityTypeORM"] = relationship("EntityTypeORM", back_populates="entities")
    aliases: Mapped[list["EntityAliasORM"]] = relationship("EntityAliasORM", back_populates="entity",
                                                             cascade="all, delete-orphan")
    keywords: Mapped[list["KeywordORM"]] = relationship("KeywordORM", back_populates="entity",
                                                          cascade="all, delete-orphan")

    def to_domain(self) -> Entity:
        return Entity(
            id=self.id,
            name=self.name,
            entity_type_id=self.entity_type_id,
            country_code=self.country_code,
            description=self.description,
            photo_url=self.photo_url,
            active=self.active,
            monitoring_type=self.monitoring_type,
            created_by=self.created_by,
            created_at=self.created_at,
            aliases=[a.to_domain() for a in self.aliases],
            keywords=[k.to_domain() for k in self.keywords],
        )

    @staticmethod
    def from_domain(e: Entity) -> "EntityORM":
        return EntityORM(
            id=str(e.id),
            name=e.name,
            entity_type_id=e.entity_type_id,
            country_code=e.country_code,
            description=e.description,
            photo_url=e.photo_url,
            active=e.active,
            monitoring_type=e.monitoring_type,
            created_by=str(e.created_by),
            created_at=e.created_at,
        )


class SocialPlatformORM(Base):
    __tablename__ = "social_platforms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    def to_domain(self) -> SocialPlatform:
        return SocialPlatform(id=self.id, name=self.name, code=self.code, active=self.active)


class TwitterFeedORM(Base):
    __tablename__ = "twitter_feeds"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    feed_type: Mapped[str] = mapped_column(String(20), nullable=False)
    term: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_domain(self) -> TwitterFeed:
        return TwitterFeed(
            id=self.id, feed_type=self.feed_type, term=self.term,
            display_name=self.display_name, entity_id=self.entity_id,
            active=self.active, created_by=self.created_by, created_at=self.created_at,
        )
