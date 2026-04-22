from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class Mention:
    id: UUID
    entity_id: UUID
    platform_id: int
    external_id: str
    content: str
    content_clean: str | None
    author_username: str | None
    author_ext_id: str | None
    url: str | None
    published_at: datetime | None
    collected_at: datetime
    language: str | None
    country_code: str | None
    sentiment_score: float | None
    sentiment_label: str | None
    hate_score: float | None
    is_hate_speech: bool
    is_relevant: bool
    reach: int
    urgency_score: float
    topic_id: int | None
    topic_label: str | None
    processed: bool
    conversation_id: str | None
    is_duplicate: bool
    media_urls: str | None
    visual_match: bool | None
    visual_match_names: str | None


@dataclass
class AccountProfile:
    id: UUID
    platform_id: int
    username: str
    external_user_id: str | None
    display_name: str | None
    account_created: datetime | None
    followers_count: int | None
    following_count: int | None
    post_count: int | None
    has_profile_photo: bool | None
    verified: bool
    bio: str | None
    location_text: str | None
    last_analyzed_at: datetime | None
    bot_probability: float | None


@dataclass
class BotAnalysis:
    id: UUID
    account_profile_id: UUID
    analyzed_at: datetime
    bot_score: float
    classification: str
    indicators: dict | None
    analyzed_by: str
