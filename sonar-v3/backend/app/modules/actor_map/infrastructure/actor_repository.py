from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.actor_map.domain.actor import Actor, ActorRelation, ActorGroup
from app.modules.actor_map.domain.ports import IActorRepository, IActorRelationRepository, IActorGroupRepository
from app.modules.actor_map.infrastructure.orm import ActorORM, ActorRelationORM, ActorGroupORM


class SqlActorRepository(IActorRepository):
    def __init__(self, db: Session):
        self._db = db

    def list(self, active_only: bool = True) -> list[Actor]:
        q = self._db.query(ActorORM)
        if active_only:
            q = q.filter(ActorORM.active == True)
        return [r.to_domain() for r in q.order_by(ActorORM.name).all()]

    def get_by_id(self, actor_id: UUID) -> Actor | None:
        row = self._db.query(ActorORM).filter(ActorORM.id == str(actor_id)).first()
        return row.to_domain() if row else None

    def create(self, actor: Actor) -> Actor:
        row = ActorORM(
            id=str(actor.id), name=actor.name, actor_type=actor.actor_type,
            party=actor.party, position=actor.position, country_code=actor.country_code,
            entity_id=str(actor.entity_id) if actor.entity_id else None, active=actor.active,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def update(self, actor: Actor) -> Actor:
        row = self._db.query(ActorORM).filter(ActorORM.id == str(actor.id)).first()
        if not row:
            return actor
        row.name = actor.name
        row.actor_type = actor.actor_type
        row.party = actor.party
        row.position = actor.position
        row.active = actor.active
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()


class SqlActorRelationRepository(IActorRelationRepository):
    def __init__(self, db: Session):
        self._db = db

    def list_all(self) -> list[ActorRelation]:
        return [r.to_domain() for r in self._db.query(ActorRelationORM).all()]

    def create(self, relation: ActorRelation) -> ActorRelation:
        row = ActorRelationORM(
            id=str(relation.id), source_id=str(relation.source_id),
            target_id=str(relation.target_id), relation_type=relation.relation_type,
            strength=relation.strength,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def delete(self, relation_id: UUID) -> None:
        self._db.query(ActorRelationORM).filter(ActorRelationORM.id == str(relation_id)).delete()
        self._db.commit()


class SqlActorGroupRepository(IActorGroupRepository):
    def __init__(self, db: Session):
        self._db = db

    def list(self) -> list[ActorGroup]:
        return [r.to_domain() for r in self._db.query(ActorGroupORM).order_by(ActorGroupORM.name).all()]

    def create(self, group: ActorGroup) -> ActorGroup:
        row = ActorGroupORM(id=str(group.id), name=group.name,
                             group_type=group.group_type, color=group.color)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()
