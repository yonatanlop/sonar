from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LegalCaseCreate(BaseModel):
    entity_id: UUID
    mention_id: UUID | None = None
    title: str
    description: str
    level: str = "platform"
    assigned_to: UUID | None = None


class LegalCasePatch(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    assigned_to: UUID | None = None


class LegalEventCreate(BaseModel):
    event_type: str
    description: str


class LegalDocumentOut(BaseModel):
    id: UUID
    file_name: str
    file_type: str
    uploaded_at: datetime


class LegalEventOut(BaseModel):
    id: UUID
    event_type: str
    description: str
    from_level: str | None = None
    to_level: str | None = None
    created_by: UUID
    created_at: datetime


class LegalCaseOut(BaseModel):
    id: UUID
    entity_id: UUID
    mention_id: UUID | None = None
    title: str
    description: str
    level: str
    status: str
    assigned_to: UUID | None = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    events: list[LegalEventOut] = []
    documents: list[LegalDocumentOut] = []
