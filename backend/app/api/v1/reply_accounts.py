from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_analyst
from app.database import get_db
from app.models.mention import Mention, SocialPlatform
from app.models.reply_account import MentionReply, ReplyAccount
from app.models.user import User

router = APIRouter(prefix="/reply-accounts", tags=["reply-accounts"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ReplyAccountCreate(BaseModel):
    platform_id: int
    username: str
    display_name: Optional[str] = None
    description: Optional[str] = None


class ReplyAccountUpdate(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None


class MentionReplyCreate(BaseModel):
    content: str
    replied_at: datetime
    external_reply_url: Optional[str] = None
    mention_url: Optional[str] = None  # si se pega la URL del post original


# ── Helpers ───────────────────────────────────────────────────────────────────

def _account_with_stats(account: ReplyAccount, db: Session) -> dict:
    total_replies = (
        db.query(func.count(MentionReply.id))
        .filter(MentionReply.reply_account_id == account.id)
        .scalar() or 0
    )
    unique_posts = (
        db.query(func.count(MentionReply.mention_id.distinct()))
        .filter(MentionReply.reply_account_id == account.id,
                MentionReply.mention_id.isnot(None))
        .scalar() or 0
    )
    last_reply = (
        db.query(func.max(MentionReply.replied_at))
        .filter(MentionReply.reply_account_id == account.id)
        .scalar()
    )
    auto_detected_count = (
        db.query(func.count(MentionReply.id))
        .filter(MentionReply.reply_account_id == account.id,
                MentionReply.auto_detected == True)  # noqa: E712
        .scalar() or 0
    )
    avg_secs = (
        db.query(
            func.avg(extract("epoch", MentionReply.replied_at - Mention.published_at))
        )
        .join(Mention, MentionReply.mention_id == Mention.id)
        .filter(
            MentionReply.reply_account_id == account.id,
            Mention.published_at.isnot(None),
        )
        .scalar()
    )
    avg_response_time_hours = round(float(avg_secs) / 3600, 1) if avg_secs else None
    return {
        "id": str(account.id),
        "username": account.username,
        "display_name": account.display_name,
        "description": account.description,
        "active": account.active,
        "created_at": account.created_at,
        "platform": {
            "id": account.platform.id,
            "name": account.platform.name,
        } if account.platform else None,
        "total_replies": total_replies,
        "unique_posts_covered": unique_posts,
        "last_reply_at": last_reply,
        "auto_detected_count": auto_detected_count,
        "manual_count": total_replies - auto_detected_count,
        "avg_response_time_hours": avg_response_time_hours,
    }


def _reply_detail(reply: MentionReply, db: Session) -> dict:
    mention_data = None
    if reply.mention:
        m = reply.mention
        plat_name = m.platform.name if m.platform else "—"
        mention_data = {
            "id": str(m.id),
            "content_preview": (m.content or "")[:150],
            "author_username": m.author_username,
            "platform": plat_name,
            "url": m.url,
        }
    logged_by_username = reply.logger.username if reply.logger else None
    response_time_hours = None
    if reply.mention and reply.mention.published_at:
        delta_secs = (reply.replied_at - reply.mention.published_at).total_seconds()
        if delta_secs >= 0:
            response_time_hours = round(delta_secs / 3600, 1)
    return {
        "id": str(reply.id),
        "content": reply.content,
        "replied_at": reply.replied_at,
        "logged_at": reply.logged_at,
        "external_reply_url": reply.external_reply_url,
        "auto_detected": reply.auto_detected,
        "response_time_hours": response_time_hours,
        "mention": mention_data,
        "logged_by_username": logged_by_username,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(db: Session = Depends(get_db),
              _: User = Depends(require_admin)):
    active_accounts = (
        db.query(func.count(ReplyAccount.id))
        .filter(ReplyAccount.active == True)  # noqa: E712
        .scalar() or 0
    )
    total_replies = db.query(func.count(MentionReply.id)).scalar() or 0
    posts_covered = (
        db.query(func.count(MentionReply.mention_id.distinct()))
        .filter(MentionReply.mention_id.isnot(None))
        .scalar() or 0
    )

    auto_detected_total = (
        db.query(func.count(MentionReply.id))
        .filter(MentionReply.auto_detected == True)  # noqa: E712
        .scalar() or 0
    )

    # Cuenta más activa
    top_row = (
        db.query(ReplyAccount.username,
                 func.count(MentionReply.id).label("cnt"))
        .outerjoin(MentionReply, MentionReply.reply_account_id == ReplyAccount.id)
        .filter(ReplyAccount.active == True)  # noqa: E712
        .group_by(ReplyAccount.id, ReplyAccount.username)
        .order_by(func.count(MentionReply.id).desc())
        .first()
    )
    top_account = {"username": top_row.username, "total_replies": top_row.cnt} \
        if top_row else None

    return {
        "active_accounts": active_accounts,
        "total_replies": total_replies,
        "posts_covered": posts_covered,
        "auto_detected_total": auto_detected_total,
        "top_account": top_account,
    }


@router.get("")
def list_accounts(db: Session = Depends(get_db),
                  _: User = Depends(require_admin)):
    accounts = (
        db.query(ReplyAccount)
        .order_by(ReplyAccount.active.desc(), ReplyAccount.created_at.desc())
        .all()
    )
    return [_account_with_stats(a, db) for a in accounts]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_account(body: ReplyAccountCreate,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(require_admin)):
    platform = db.query(SocialPlatform).filter(
        SocialPlatform.id == body.platform_id
    ).first()
    if not platform:
        raise HTTPException(status_code=404, detail="Plataforma no encontrada")

    account = ReplyAccount(
        platform_id=body.platform_id,
        username=body.username.lstrip("@"),
        display_name=body.display_name,
        description=body.description,
        created_by=current_user.id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return _account_with_stats(account, db)


@router.put("/{account_id}")
def update_account(account_id: UUID,
                   body: ReplyAccountUpdate,
                   db: Session = Depends(get_db),
                   _: User = Depends(require_admin)):
    account = db.query(ReplyAccount).filter(ReplyAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    if body.username is not None:
        account.username = body.username.lstrip("@")
    if body.display_name is not None:
        account.display_name = body.display_name
    if body.description is not None:
        account.description = body.description
    if body.active is not None:
        account.active = body.active

    db.commit()
    db.refresh(account)
    return _account_with_stats(account, db)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: UUID,
                   db: Session = Depends(get_db),
                   _: User = Depends(require_admin)):
    account = db.query(ReplyAccount).filter(ReplyAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    db.delete(account)
    db.commit()


@router.get("/{account_id}/replies")
def list_replies(account_id: UUID,
                 db: Session = Depends(get_db),
                 _: User = Depends(require_admin)):
    account = db.query(ReplyAccount).filter(ReplyAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    replies = (
        db.query(MentionReply)
        .filter(MentionReply.reply_account_id == account_id)
        .order_by(MentionReply.replied_at.desc())
        .all()
    )
    return [_reply_detail(r, db) for r in replies]


@router.post("/{account_id}/replies", status_code=status.HTTP_201_CREATED)
def log_reply(account_id: UUID,
              body: MentionReplyCreate,
              db: Session = Depends(get_db),
              current_user: User = Depends(require_analyst)):
    account = db.query(ReplyAccount).filter(ReplyAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    # Intentar resolver mention_id por URL si se proporcionó
    mention_id = None
    if body.mention_url:
        mention = db.query(Mention).filter(
            Mention.url == body.mention_url
        ).first()
        if mention:
            mention_id = mention.id

    reply = MentionReply(
        reply_account_id=account_id,
        mention_id=mention_id,
        content=body.content,
        replied_at=body.replied_at,
        external_reply_url=body.external_reply_url,
        logged_by=current_user.id,
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return _reply_detail(reply, db)
