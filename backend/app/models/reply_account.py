import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ReplyAccount(Base):
    __tablename__ = "reply_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    platform_id: Mapped[int] = mapped_column(Integer,
                                              ForeignKey("social_platforms.id"),
                                              nullable=False)
    username: Mapped[str] = mapped_column(String(150), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                                   ForeignKey("users.id"),
                                                   nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now(),
                                                  nullable=False)

    platform: Mapped["SocialPlatform"] = relationship("SocialPlatform")  # noqa: F821
    replies: Mapped[list["MentionReply"]] = relationship(
        "MentionReply", back_populates="account", cascade="all, delete-orphan"
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821


class MentionReply(Base):
    __tablename__ = "mention_replies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    reply_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                                         ForeignKey("reply_accounts.id",
                                                                    ondelete="CASCADE"),
                                                         nullable=False)
    mention_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True),
                                                          ForeignKey("mentions.id",
                                                                     ondelete="SET NULL"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    replied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    external_reply_url: Mapped[str | None] = mapped_column(String(1000))
    logged_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                                  ForeignKey("users.id"),
                                                  nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now(),
                                                 nullable=False)

    account: Mapped["ReplyAccount"] = relationship("ReplyAccount",
                                                    back_populates="replies")
    mention: Mapped["Mention | None"] = relationship("Mention")  # noqa: F821
    logger: Mapped["User"] = relationship("User", foreign_keys=[logged_by])  # noqa: F821
