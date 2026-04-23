from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.modules.collection.domain.mention import Mention, AccountProfile, BotAnalysis


class IMentionRepository(ABC):
    @abstractmethod
    def get_by_id(self, mention_id: UUID) -> Mention | None: ...

    @abstractmethod
    def exists(self, platform_id: int, external_id: str) -> bool: ...

    @abstractmethod
    def create(self, mention: Mention) -> Mention: ...

    @abstractmethod
    def update(self, mention: Mention) -> Mention: ...

    @abstractmethod
    def list_unprocessed(self, limit: int = 100) -> list[Mention]: ...

    @abstractmethod
    def list_by_entity(self, entity_id: UUID, since: datetime, limit: int = 200) -> list[Mention]: ...

    @abstractmethod
    def count_by_entity_since(self, entity_id: UUID, since: datetime) -> int: ...

    @abstractmethod
    def delete_older_than(self, cutoff: datetime) -> int: ...


class IAccountProfileRepository(ABC):
    @abstractmethod
    def get_by_platform_user(self, platform_id: int, external_user_id: str) -> AccountProfile | None: ...

    @abstractmethod
    def upsert(self, profile: AccountProfile) -> AccountProfile: ...


class IMentionQueryService(ABC):
    """Port consumed by alerting and intelligence modules."""

    @abstractmethod
    def count_in_window(self, entity_id: UUID, window_minutes: int) -> int: ...

    @abstractmethod
    def negative_pct_in_window(self, entity_id: UUID, window_minutes: int) -> float: ...

    @abstractmethod
    def bot_count_in_window(self, entity_id: UUID, window_minutes: int) -> int: ...

    @abstractmethod
    def historical_average(self, entity_id: UUID, window_minutes: int) -> float: ...

    @abstractmethod
    def keyword_critical_count(self, entity_id: UUID, window_minutes: int) -> int: ...

    @abstractmethod
    def hate_speech_count(self, entity_id: UUID, window_minutes: int) -> int: ...
