from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.shared.types import MonitoringType


@dataclass
class EntityType:
    id: int
    name: str


@dataclass
class EntityAlias:
    id: UUID
    entity_id: UUID
    alias: str
    created_by: UUID
    created_at: datetime


@dataclass
class Keyword:
    id: UUID
    entity_id: UUID
    keyword: str
    language: str
    weight: int
    active: bool
    created_by: UUID
    created_at: datetime


@dataclass
class Entity:
    id: UUID
    name: str
    entity_type_id: int
    country_code: str | None
    description: str | None
    photo_url: str | None
    active: bool
    monitoring_type: str | None
    created_by: UUID
    created_at: datetime
    aliases: list[EntityAlias] = field(default_factory=list)
    keywords: list[Keyword] = field(default_factory=list)


@dataclass
class TwitterFeed:
    id: UUID
    feed_type: str
    term: str
    display_name: str
    entity_id: UUID | None
    active: bool
    created_by: UUID
    created_at: datetime


@dataclass
class SocialPlatform:
    id: int
    name: str
    code: str
    active: bool


@dataclass
class Country:
    code: str
    name: str
