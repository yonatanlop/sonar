import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    metric: Mapped[str] = mapped_column(String(30), nullable=False)   # "volume" | "negative_pct"
    z_score: Mapped[float] = mapped_column(Float, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)        # valor actual
    baseline: Mapped[float] = mapped_column(Float, nullable=False)     # media histórica
    std_dev: Mapped[float] = mapped_column(Float, nullable=False)      # desviación estándar

    entity: Mapped["Entity"] = relationship("Entity")
