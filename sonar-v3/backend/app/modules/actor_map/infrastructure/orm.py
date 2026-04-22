from uuid import uuid4

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, SmallInteger, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database import Base
from app.modules.actor_map.domain.actor import Actor, ActorRelation, ActorGroup

actor_group_members = Table(
    "actor_group_members",
    Base.metadata,
    Column("actor_id", String(36), ForeignKey("actors.id"), primary_key=True),
    Column("group_id", String(36), ForeignKey("actor_groups.id"), primary_key=True),
    Column("role", String(50), nullable=True),
)


class ActorORM(Base):
    __tablename__ = "actors"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_type: Mapped[str] = mapped_column(
        Enum("politician", "organization", "media", "influencer", name="actor_type"),
        nullable=False,
    )
    party: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position: Mapped[str | None] = mapped_column(String(200), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), ForeignKey("countries.code"), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("entities.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    groups: Mapped[list["ActorGroupORM"]] = relationship("ActorGroupORM", secondary=actor_group_members)

    def to_domain(self) -> Actor:
        return Actor(
            id=self.id, name=self.name, actor_type=self.actor_type,
            party=self.party, position=self.position, country_code=self.country_code,
            entity_id=self.entity_id, active=self.active,
        )


class ActorRelationORM(Base):
    __tablename__ = "actor_relations"
    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "relation_type", name="uq_actor_relation"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("actors.id"), nullable=False)
    target_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("actors.id"), nullable=False)
    relation_type: Mapped[str] = mapped_column(
        Enum("ally", "opponent", "financed_by", "member_of", name="relation_type"),
        nullable=False,
    )
    strength: Mapped[int] = mapped_column(SmallInteger, default=1)

    def to_domain(self) -> ActorRelation:
        return ActorRelation(
            id=self.id, source_id=self.source_id, target_id=self.target_id,
            relation_type=self.relation_type, strength=self.strength,
        )


class ActorGroupORM(Base):
    __tablename__ = "actor_groups"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    group_type: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#6366f1")

    def to_domain(self) -> ActorGroup:
        return ActorGroup(id=self.id, name=self.name, group_type=self.group_type, color=self.color)
