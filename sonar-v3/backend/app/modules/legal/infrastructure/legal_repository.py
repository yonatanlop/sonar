from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.legal.domain.legal_case import LegalCase, LegalEvent, LegalDocument
from app.modules.legal.domain.ports import ILegalCaseRepository, ILegalEventRepository, ILegalDocumentRepository
from app.modules.legal.infrastructure.orm import LegalCaseORM, LegalEventORM, LegalDocumentORM


class SqlLegalCaseRepository(ILegalCaseRepository):
    def __init__(self, db: Session):
        self._db = db

    def list(self, level=None, status=None, entity_id=None) -> list[LegalCase]:
        q = self._db.query(LegalCaseORM)
        if level:
            q = q.filter(LegalCaseORM.level == level)
        if status:
            q = q.filter(LegalCaseORM.status == status)
        if entity_id:
            q = q.filter(LegalCaseORM.entity_id == str(entity_id))
        return [r.to_domain() for r in q.order_by(LegalCaseORM.created_at.desc()).all()]

    def get_by_id(self, case_id: UUID) -> LegalCase | None:
        row = self._db.query(LegalCaseORM).filter(LegalCaseORM.id == str(case_id)).first()
        return row.to_domain() if row else None

    def create(self, case: LegalCase) -> LegalCase:
        row = LegalCaseORM(
            id=str(case.id), mention_id=str(case.mention_id) if case.mention_id else None,
            entity_id=str(case.entity_id), title=case.title, description=case.description,
            level=case.level, status=case.status,
            assigned_to=str(case.assigned_to) if case.assigned_to else None,
            created_by=str(case.created_by), created_at=case.created_at, updated_at=case.updated_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def update(self, case: LegalCase) -> LegalCase:
        row = self._db.query(LegalCaseORM).filter(LegalCaseORM.id == str(case.id)).first()
        if not row:
            return case
        row.title = case.title
        row.description = case.description
        row.status = case.status
        row.level = case.level
        row.assigned_to = str(case.assigned_to) if case.assigned_to else None
        row.updated_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()


class SqlLegalEventRepository(ILegalEventRepository):
    def __init__(self, db: Session):
        self._db = db

    def list_by_case(self, case_id: UUID) -> list[LegalEvent]:
        rows = (
            self._db.query(LegalEventORM)
            .filter(LegalEventORM.case_id == str(case_id))
            .order_by(LegalEventORM.created_at.asc())
            .all()
        )
        return [r.to_domain() for r in rows]

    def create(self, event: LegalEvent) -> LegalEvent:
        row = LegalEventORM(
            id=str(event.id), case_id=str(event.case_id), event_type=event.event_type,
            description=event.description, from_level=event.from_level, to_level=event.to_level,
            created_by=str(event.created_by), created_at=event.created_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()


class SqlLegalDocumentRepository(ILegalDocumentRepository):
    def __init__(self, db: Session):
        self._db = db

    def list_by_case(self, case_id: UUID) -> list[LegalDocument]:
        rows = self._db.query(LegalDocumentORM).filter(LegalDocumentORM.case_id == str(case_id)).all()
        return [r.to_domain() for r in rows]

    def create(self, doc: LegalDocument) -> LegalDocument:
        row = LegalDocumentORM(
            id=str(doc.id), case_id=str(doc.case_id), file_name=doc.file_name,
            file_path=doc.file_path, file_type=doc.file_type,
            uploaded_by=str(doc.uploaded_by), uploaded_at=doc.uploaded_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def delete(self, doc_id: UUID) -> None:
        self._db.query(LegalDocumentORM).filter(LegalDocumentORM.id == str(doc_id)).delete()
        self._db.commit()
