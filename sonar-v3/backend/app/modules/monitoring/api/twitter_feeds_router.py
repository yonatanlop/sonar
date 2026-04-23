from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.shared.deps import get_db, get_current_user, require_analyst
from app.modules.monitoring.application.schemas import TwitterFeedCreate, TwitterFeedOut
from app.modules.monitoring.application.monitoring_service import TwitterFeedService
from app.modules.monitoring.infrastructure.entity_repository import (
    SqlTwitterFeedRepository, SqlEntityRepository
)

router = APIRouter(prefix="/twitter-feeds", tags=["Twitter Explorer"])


def _svc(db: Session = Depends(get_db)) -> TwitterFeedService:
    return TwitterFeedService(SqlTwitterFeedRepository(db), SqlEntityRepository(db))


@router.get("", response_model=list[TwitterFeedOut])
def list_feeds(svc: TwitterFeedService = Depends(_svc), _=Depends(get_current_user)):
    return [TwitterFeedOut(
        id=f.id, feed_type=f.feed_type, term=f.term, display_name=f.display_name,
        entity_id=f.entity_id, active=f.active, created_at=f.created_at,
    ) for f in svc.list()]


@router.post("", response_model=TwitterFeedOut, status_code=201)
def create_feed(
    data: TwitterFeedCreate,
    svc: TwitterFeedService = Depends(_svc),
    current_user=Depends(require_analyst),
):
    f = svc.create(data, created_by=current_user.id)
    return TwitterFeedOut(
        id=f.id, feed_type=f.feed_type, term=f.term, display_name=f.display_name,
        entity_id=f.entity_id, active=f.active, created_at=f.created_at,
    )


@router.patch("/{feed_id}/toggle", response_model=TwitterFeedOut)
def toggle_feed(feed_id: UUID, svc: TwitterFeedService = Depends(_svc), _=Depends(require_analyst)):
    f = svc.toggle(feed_id)
    return TwitterFeedOut(
        id=f.id, feed_type=f.feed_type, term=f.term, display_name=f.display_name,
        entity_id=f.entity_id, active=f.active, created_at=f.created_at,
    )


@router.delete("/{feed_id}", status_code=204)
def delete_feed(feed_id: UUID, svc: TwitterFeedService = Depends(_svc), _=Depends(require_analyst)):
    svc.delete(feed_id)
