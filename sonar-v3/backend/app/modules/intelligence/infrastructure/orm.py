from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base
from app.modules.intelligence.domain.analysis import Anomaly, TrendForecast, DailySummary


class AnomalyORM(Base):
    __tablename__ = "anomalies"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    entity_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("entities.id"), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    metric: Mapped[str] = mapped_column(String(30), nullable=False)
    z_score: Mapped[float] = mapped_column(Float, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    baseline: Mapped[float] = mapped_column(Float, nullable=False)
    std_dev: Mapped[float] = mapped_column(Float, nullable=False)
    context_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_domain(self) -> Anomaly:
        return Anomaly(
            id=self.id, entity_id=self.entity_id, detected_at=self.detected_at,
            metric=self.metric, z_score=self.z_score, value=self.value,
            baseline=self.baseline, std_dev=self.std_dev,
            context_explanation=self.context_explanation,
        )


class TrendForecastORM(Base):
    __tablename__ = "trend_forecasts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    entity_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                            ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    predicted_count: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_low: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_high: Mapped[float] = mapped_column(Float, nullable=False)
    model_used: Mapped[str] = mapped_column(String(50), nullable=False, default="holt_damped")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def to_domain(self) -> TrendForecast:
        return TrendForecast(
            id=self.id, entity_id=self.entity_id, forecast_date=self.forecast_date,
            predicted_count=self.predicted_count, confidence_low=self.confidence_low,
            confidence_high=self.confidence_high, model_used=self.model_used,
            generated_at=self.generated_at,
        )


class DailySummaryORM(Base):
    __tablename__ = "daily_summaries"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    entity_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("entities.id"), nullable=False)
    summary_date: Mapped[date] = mapped_column(Date, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str] = mapped_column(String(80), nullable=False)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_domain(self) -> DailySummary:
        return DailySummary(
            id=self.id, entity_id=self.entity_id, summary_date=self.summary_date,
            summary_text=self.summary_text, model_used=self.model_used,
            mention_count=self.mention_count, generated_at=self.generated_at,
        )
