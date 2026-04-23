from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.shared.types import LegalCaseLevel, LegalCaseStatus


@dataclass
class LegalCase:
    id: UUID
    mention_id: UUID | None
    entity_id: UUID
    title: str
    description: str
    level: str
    status: str
    assigned_to: UUID | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime


@dataclass
class LegalEvent:
    id: UUID
    case_id: UUID
    event_type: str
    description: str
    from_level: str | None
    to_level: str | None
    created_by: UUID
    created_at: datetime


@dataclass
class LegalDocument:
    id: UUID
    case_id: UUID
    file_name: str
    file_path: str
    file_type: str
    uploaded_by: UUID
    uploaded_at: datetime
