import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TrendForecast(Base):
    __tablename__ = "trend_forecasts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    predicted_count: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_low: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_high: Mapped[float] = mapped_column(Float, nullable=False)
    model_used: Mapped[str] = mapped_column(String(50), nullable=False, default="holt_damped")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    entity: Mapped["Entity"] = relationship("Entity")
