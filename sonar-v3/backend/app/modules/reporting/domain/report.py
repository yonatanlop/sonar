from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass
class Report:
    id: UUID
    name: str
    report_type: str
    entity_id: UUID | None
    country_code: str | None
    date_from: date
    date_to: date
    parameters: dict | None
    file_path: str | None
    created_by: UUID
    created_at: datetime
