from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.monitoring.domain.ports import IEntityQueryService
from app.modules.monitoring.infrastructure.orm import EntityORM, KeywordORM


class SqlEntityQueryService(IEntityQueryService):
    def __init__(self, db: Session):
        self._db = db

    def get_name(self, entity_id: UUID) -> str | None:
        row = self._db.query(EntityORM.name).filter(EntityORM.id == str(entity_id)).first()
        return row[0] if row else None

    def get_active_keywords(self) -> list[dict]:
        rows = (
            self._db.query(KeywordORM)
            .filter(KeywordORM.active == True)
            .all()
        )
        return [
            {"id": r.id, "entity_id": r.entity_id, "keyword": r.keyword,
             "language": r.language, "weight": r.weight}
            for r in rows
        ]
