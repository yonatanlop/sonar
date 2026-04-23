from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.collection.domain.mention import Mention, AccountProfile
from app.modules.collection.domain.ports import IMentionRepository, IAccountProfileRepository, IMentionQueryService
from app.modules.collection.infrastructure.orm import MentionORM, AccountProfileORM


class SqlMentionRepository(IMentionRepository):
    def __init__(self, db: Session):
        self._db = db

    def get_by_id(self, mention_id: UUID) -> Mention | None:
        row = self._db.query(MentionORM).filter(MentionORM.id == str(mention_id)).first()
        return row.to_domain() if row else None

    def exists(self, platform_id: int, external_id: str) -> bool:
        return self._db.query(MentionORM.id).filter(
            MentionORM.platform_id == platform_id,
            MentionORM.external_id == external_id,
        ).first() is not None

    def create(self, mention: Mention) -> Mention:
        row = MentionORM(
            id=str(mention.id), entity_id=str(mention.entity_id),
            platform_id=mention.platform_id, external_id=mention.external_id,
            content=mention.content, content_clean=mention.content_clean,
            author_username=mention.author_username, author_ext_id=mention.author_ext_id,
            url=mention.url, published_at=mention.published_at, collected_at=mention.collected_at,
            language=mention.language, country_code=mention.country_code,
            reach=mention.reach, conversation_id=mention.conversation_id,
            media_urls=mention.media_urls,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def update(self, mention: Mention) -> Mention:
        row = self._db.query(MentionORM).filter(MentionORM.id == str(mention.id)).first()
        if not row:
            return mention
        row.content_clean = mention.content_clean
        row.language = mention.language
        row.country_code = mention.country_code
        row.sentiment_score = mention.sentiment_score
        row.sentiment_label = mention.sentiment_label
        row.hate_score = mention.hate_score
        row.is_hate_speech = mention.is_hate_speech
        row.is_relevant = mention.is_relevant
        row.urgency_score = mention.urgency_score
        row.topic_id = mention.topic_id
        row.topic_label = mention.topic_label
        row.processed = mention.processed
        row.is_duplicate = mention.is_duplicate
        row.visual_match = mention.visual_match
        row.visual_match_names = mention.visual_match_names
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def list_unprocessed(self, limit: int = 100) -> list[Mention]:
        rows = (
            self._db.query(MentionORM)
            .filter(MentionORM.processed == False, MentionORM.is_duplicate == False)
            .order_by(MentionORM.collected_at.asc())
            .limit(limit)
            .all()
        )
        return [r.to_domain() for r in rows]

    def list_by_entity(self, entity_id: UUID, since: datetime, limit: int = 200) -> list[Mention]:
        rows = (
            self._db.query(MentionORM)
            .filter(MentionORM.entity_id == str(entity_id), MentionORM.collected_at >= since)
            .order_by(MentionORM.collected_at.desc())
            .limit(limit)
            .all()
        )
        return [r.to_domain() for r in rows]

    def count_by_entity_since(self, entity_id: UUID, since: datetime) -> int:
        return self._db.query(func.count(MentionORM.id)).filter(
            MentionORM.entity_id == str(entity_id),
            MentionORM.collected_at >= since,
        ).scalar() or 0

    def delete_older_than(self, cutoff: datetime) -> int:
        count = self._db.query(MentionORM).filter(MentionORM.collected_at < cutoff).count()
        self._db.query(MentionORM).filter(MentionORM.collected_at < cutoff).delete()
        self._db.commit()
        return count


class SqlAccountProfileRepository(IAccountProfileRepository):
    def __init__(self, db: Session):
        self._db = db

    def get_by_platform_user(self, platform_id: int, external_user_id: str) -> AccountProfile | None:
        row = self._db.query(AccountProfileORM).filter(
            AccountProfileORM.platform_id == platform_id,
            AccountProfileORM.external_user_id == external_user_id,
        ).first()
        return row.to_domain() if row else None

    def upsert(self, profile: AccountProfile) -> AccountProfile:
        existing = self.get_by_platform_user(profile.platform_id, profile.external_user_id)
        if existing:
            row = self._db.query(AccountProfileORM).filter(
                AccountProfileORM.id == str(existing.id)
            ).first()
            row.username = profile.username
            row.display_name = profile.display_name
            row.followers_count = profile.followers_count
            row.following_count = profile.following_count
            row.post_count = profile.post_count
            row.verified = profile.verified
            row.bio = profile.bio
            row.location_text = profile.location_text
            row.last_analyzed_at = profile.last_analyzed_at
            self._db.commit()
            self._db.refresh(row)
            return row.to_domain()
        row = AccountProfileORM(
            id=str(profile.id), platform_id=profile.platform_id,
            username=profile.username, external_user_id=profile.external_user_id,
            display_name=profile.display_name, account_created=profile.account_created,
            followers_count=profile.followers_count, following_count=profile.following_count,
            post_count=profile.post_count, has_profile_photo=profile.has_profile_photo,
            verified=profile.verified, bio=profile.bio, location_text=profile.location_text,
            last_analyzed_at=profile.last_analyzed_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()


class SqlMentionQueryService(IMentionQueryService):
    """Implements the cross-module port consumed by alerting and intelligence."""

    def __init__(self, db: Session):
        self._db = db

    def _since(self, window_minutes: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

    def count_in_window(self, entity_id: UUID, window_minutes: int) -> int:
        return self._db.query(func.count(MentionORM.id)).filter(
            MentionORM.entity_id == str(entity_id),
            MentionORM.collected_at >= self._since(window_minutes),
        ).scalar() or 0

    def negative_pct_in_window(self, entity_id: UUID, window_minutes: int) -> float:
        since = self._since(window_minutes)
        total = self._db.query(func.count(MentionORM.id)).filter(
            MentionORM.entity_id == str(entity_id),
            MentionORM.collected_at >= since,
        ).scalar() or 0
        if total == 0:
            return 0.0
        neg = self._db.query(func.count(MentionORM.id)).filter(
            MentionORM.entity_id == str(entity_id),
            MentionORM.collected_at >= since,
            MentionORM.sentiment_label.in_(["negative", "very_negative"]),
        ).scalar() or 0
        return (neg / total) * 100

    def bot_count_in_window(self, entity_id: UUID, window_minutes: int) -> int:
        from app.modules.collection.infrastructure.orm import AccountProfileORM
        since = self._since(window_minutes)
        bot_users = self._db.query(MentionORM.author_ext_id).filter(
            MentionORM.entity_id == str(entity_id),
            MentionORM.collected_at >= since,
            MentionORM.author_ext_id.isnot(None),
        ).distinct().subquery()
        return self._db.query(func.count(AccountProfileORM.id)).filter(
            AccountProfileORM.external_user_id.in_(bot_users),
            AccountProfileORM.bot_probability >= 0.7,
        ).scalar() or 0

    def historical_average(self, entity_id: UUID, window_minutes: int) -> float:
        periods = 7
        window_td = timedelta(minutes=window_minutes)
        now = datetime.now(timezone.utc)
        counts = []
        for i in range(1, periods + 1):
            end = now - (i - 1) * window_td
            start = end - window_td
            c = self._db.query(func.count(MentionORM.id)).filter(
                MentionORM.entity_id == str(entity_id),
                MentionORM.collected_at >= start,
                MentionORM.collected_at < end,
            ).scalar() or 0
            counts.append(c)
        return sum(counts) / len(counts) if counts else 0.0

    def keyword_critical_count(self, entity_id: UUID, window_minutes: int) -> int:
        from app.modules.collection.infrastructure.orm import mention_keywords
        from app.modules.monitoring.infrastructure.orm import KeywordORM
        since = self._since(window_minutes)
        return self._db.query(func.count(MentionORM.id)).join(
            mention_keywords, MentionORM.id == mention_keywords.c.mention_id
        ).join(
            KeywordORM, KeywordORM.id == mention_keywords.c.keyword_id
        ).filter(
            MentionORM.entity_id == str(entity_id),
            MentionORM.collected_at >= since,
            KeywordORM.weight >= 3,
        ).scalar() or 0

    def hate_speech_count(self, entity_id: UUID, window_minutes: int) -> int:
        return self._db.query(func.count(MentionORM.id)).filter(
            MentionORM.entity_id == str(entity_id),
            MentionORM.collected_at >= self._since(window_minutes),
            MentionORM.is_hate_speech == True,
        ).scalar() or 0
