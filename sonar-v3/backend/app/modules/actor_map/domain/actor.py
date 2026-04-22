from dataclasses import dataclass, field
from uuid import UUID

from app.shared.types import ActorType, RelationType


@dataclass
class Actor:
    id: UUID
    name: str
    actor_type: str
    party: str | None
    position: str | None
    country_code: str | None
    entity_id: UUID | None
    active: bool


@dataclass
class ActorRelation:
    id: UUID
    source_id: UUID
    target_id: UUID
    relation_type: str
    strength: int


@dataclass
class ActorGroup:
    id: UUID
    name: str
    group_type: str
    color: str
