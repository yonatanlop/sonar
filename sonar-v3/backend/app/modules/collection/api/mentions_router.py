from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.shared.deps import get_db, get_current_user
from app.modules.collection.application.schemas import MentionOut
from app.modules.collection.infrastructure.mention_repository import SqlMentionRepository
from app.modules.collection.infrastructure.orm import MentionORM

router = APIRouter(prefix="/mentions", tags=["Menciones"])


@router.get("", response_model=list[MentionOut])
def list_mentions(
    entity_id: UUID | None = Query(None),
    platform_id: int | None = Query(None),
    sentiment_label: str | None = Query(None),
    is_hate_speech: bool | None = Query(None),
    since_hours: int = Query(24),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    q = db.query(MentionORM).filter(MentionORM.collected_at >= since)
    if entity_id:
        q = q.filter(MentionORM.entity_id == str(entity_id))
    if platform_id:
        q = q.filter(MentionORM.platform_id == platform_id)
    if sentiment_label:
        q = q.filter(MentionORM.sentiment_label == sentiment_label)
    if is_hate_speech is not None:
        q = q.filter(MentionORM.is_hate_speech == is_hate_speech)
    rows = q.order_by(MentionORM.collected_at.desc()).offset(offset).limit(limit).all()
    return [_to_out(r) for r in rows]


@router.get("/{mention_id}", response_model=MentionOut)
def get_mention(mention_id: UUID, db: Session = Depends(get_db), _=Depends(get_current_user)):
    from app.shared.exceptions import NotFoundError
    repo = SqlMentionRepository(db)
    m = repo.get_by_id(mention_id)
    if not m:
        raise NotFoundError("Mención no encontrada")
    return _to_out_domain(m)


def _to_out(row: MentionORM) -> MentionOut:
    return MentionOut(
        id=row.id, entity_id=row.entity_id, platform_id=row.platform_id,
        external_id=row.external_id, content=row.content,
        author_username=row.author_username, url=row.url,
        published_at=row.published_at, collected_at=row.collected_at,
        language=row.language, country_code=row.country_code,
        sentiment_label=row.sentiment_label,
        sentiment_score=float(row.sentiment_score) if row.sentiment_score else None,
        hate_score=float(row.hate_score) if row.hate_score else None,
        is_hate_speech=row.is_hate_speech, is_relevant=row.is_relevant,
        reach=row.reach,
        urgency_score=float(row.urgency_score) if row.urgency_score else 0,
        topic_label=row.topic_label, processed=row.processed,
        is_duplicate=row.is_duplicate, conversation_id=row.conversation_id,
    )


def _to_out_domain(m) -> MentionOut:
    return MentionOut(
        id=m.id, entity_id=m.entity_id, platform_id=m.platform_id,
        external_id=m.external_id, content=m.content,
        author_username=m.author_username, url=m.url,
        published_at=m.published_at, collected_at=m.collected_at,
        language=m.language, country_code=m.country_code,
        sentiment_label=m.sentiment_label, sentiment_score=m.sentiment_score,
        hate_score=m.hate_score, is_hate_speech=m.is_hate_speech,
        is_relevant=m.is_relevant, reach=m.reach, urgency_score=m.urgency_score,
        topic_label=m.topic_label, processed=m.processed,
        is_duplicate=m.is_duplicate, conversation_id=m.conversation_id,
    )
