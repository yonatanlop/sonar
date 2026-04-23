from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MentionOut(BaseModel):
    id: UUID
    entity_id: UUID
    platform_id: int
    external_id: str
    content: str
    author_username: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    collected_at: datetime
    language: str | None = None
    country_code: str | None = None
    sentiment_label: str | None = None
    sentiment_score: float | None = None
    hate_score: float | None = None
    is_hate_speech: bool = False
    is_relevant: bool = True
    reach: int = 0
    urgency_score: float = 0
    topic_label: str | None = None
    processed: bool = False
    is_duplicate: bool = False
    conversation_id: str | None = None

    model_config = {"from_attributes": True}


class MentionFilter(BaseModel):
    entity_id: UUID | None = None
    platform_id: int | None = None
    sentiment_label: str | None = None
    is_hate_speech: bool | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int = 50
    offset: int = 0


class AccountProfileOut(BaseModel):
    id: UUID
    platform_id: int
    username: str
    display_name: str | None = None
    followers_count: int | None = None
    verified: bool = False
    bot_probability: float | None = None

    model_config = {"from_attributes": True}
