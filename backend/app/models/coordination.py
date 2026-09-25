import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CoordinationCluster(Base):
    """
    Grupo de actividad coordinada detectado: varias cuentas publicando el mismo texto (o casi) en una
    ventana corta ("red"), o una sola cuenta repitiendo el mismo texto muchas veces ("repeticion").

    Es un CANDIDATO: el equipo lo revisa y lo marca confirmado/descartado (`status`). Esas decisiones
    son la referencia real para calibrar el detector (ver workers/analytics/coordination.py).
    """
    __tablename__ = "coordination_clusters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)          # red | repeticion
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=True)
    entity_name: Mapped[str | None] = mapped_column(String(200))
    platform: Mapped[str | None] = mapped_column(String(50))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accounts_count: Mapped[int] = mapped_column(Integer, nullable=False)
    mentions_count: Mapped[int] = mapped_column(Integer, nullable=False)
    span_hours: Mapped[float] = mapped_column(Float, default=0)
    median_followers: Mapped[int | None] = mapped_column(Integer)
    low_follower_share: Mapped[float] = mapped_column(Float, default=0)    # cuentas con < 300 seguidores
    score: Mapped[float] = mapped_column(Float, nullable=False, index=True)  # 0-1
    sentiment_mix: Mapped[dict | None] = mapped_column(JSONB)
    sample_text: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="nuevo", index=True)  # nuevo|confirmado|descartado
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)

    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    members: Mapped[list["CoordinationMember"]] = relationship(
        "CoordinationMember", back_populates="cluster", cascade="all, delete-orphan",
        order_by="CoordinationMember.published_at",
    )
    reviewer: Mapped["User"] = relationship("User", foreign_keys=[reviewed_by])  # noqa: F821


class CoordinationMember(Base):
    """Una publicación dentro de un grupo coordinado (con datos de la cuenta al momento de detectarla)."""
    __tablename__ = "coordination_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coordination_clusters.id", ondelete="CASCADE"), nullable=False, index=True)
    mention_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mentions.id", ondelete="CASCADE"), nullable=False, index=True)
    account_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("account_profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    author_username: Mapped[str | None] = mapped_column(String(150))
    author_ext_id: Mapped[str | None] = mapped_column(String(150), index=True)
    followers: Mapped[int | None] = mapped_column(Integer)
    account_created: Mapped[date | None] = mapped_column(Date)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sentiment: Mapped[str | None] = mapped_column(String(20))
    content_preview: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(1000))

    cluster: Mapped["CoordinationCluster"] = relationship("CoordinationCluster", back_populates="members")
