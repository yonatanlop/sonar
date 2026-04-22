from datetime import date, datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.intelligence.domain.analysis import Anomaly, TrendForecast, DailySummary
from app.modules.intelligence.domain.ports import (
    IAnomalyRepository, ITrendForecastRepository, IDailySummaryRepository
)
from app.modules.intelligence.infrastructure.orm import AnomalyORM, TrendForecastORM, DailySummaryORM


class SqlAnomalyRepository(IAnomalyRepository):
    def __init__(self, db: Session):
        self._db = db

    def create(self, anomaly: Anomaly) -> Anomaly:
        row = AnomalyORM(
            id=str(anomaly.id), entity_id=str(anomaly.entity_id),
            detected_at=anomaly.detected_at, metric=anomaly.metric,
            z_score=anomaly.z_score, value=anomaly.value,
            baseline=anomaly.baseline, std_dev=anomaly.std_dev,
            context_explanation=anomaly.context_explanation,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def list_by_entity(self, entity_id: UUID, limit: int = 20) -> list[Anomaly]:
        rows = (
            self._db.query(AnomalyORM)
            .filter(AnomalyORM.entity_id == str(entity_id))
            .order_by(AnomalyORM.detected_at.desc())
            .limit(limit)
            .all()
        )
        return [r.to_domain() for r in rows]

    def list_recent(self, hours: int = 24) -> list[Anomaly]:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        rows = (
            self._db.query(AnomalyORM)
            .filter(AnomalyORM.detected_at >= since)
            .order_by(AnomalyORM.detected_at.desc())
            .all()
        )
        return [r.to_domain() for r in rows]


class SqlTrendForecastRepository(ITrendForecastRepository):
    def __init__(self, db: Session):
        self._db = db

    def create(self, forecast: TrendForecast) -> TrendForecast:
        row = TrendForecastORM(
            id=str(forecast.id), entity_id=str(forecast.entity_id),
            forecast_date=forecast.forecast_date, predicted_count=forecast.predicted_count,
            confidence_low=forecast.confidence_low, confidence_high=forecast.confidence_high,
            model_used=forecast.model_used, generated_at=forecast.generated_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def list_by_entity(self, entity_id: UUID, from_date: date) -> list[TrendForecast]:
        rows = (
            self._db.query(TrendForecastORM)
            .filter(TrendForecastORM.entity_id == str(entity_id),
                    TrendForecastORM.forecast_date >= from_date)
            .order_by(TrendForecastORM.forecast_date.asc())
            .all()
        )
        return [r.to_domain() for r in rows]

    def delete_older_than(self, cutoff: date) -> int:
        count = self._db.query(TrendForecastORM).filter(TrendForecastORM.forecast_date < cutoff).count()
        self._db.query(TrendForecastORM).filter(TrendForecastORM.forecast_date < cutoff).delete()
        self._db.commit()
        return count


class SqlDailySummaryRepository(IDailySummaryRepository):
    def __init__(self, db: Session):
        self._db = db

    def create(self, summary: DailySummary) -> DailySummary:
        row = DailySummaryORM(
            id=str(summary.id), entity_id=str(summary.entity_id),
            summary_date=summary.summary_date, summary_text=summary.summary_text,
            model_used=summary.model_used, mention_count=summary.mention_count,
            generated_at=summary.generated_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def get_by_entity_date(self, entity_id: UUID, summary_date: date) -> DailySummary | None:
        row = self._db.query(DailySummaryORM).filter(
            DailySummaryORM.entity_id == str(entity_id),
            DailySummaryORM.summary_date == summary_date,
        ).first()
        return row.to_domain() if row else None

    def list_by_entity(self, entity_id: UUID, limit: int = 30) -> list[DailySummary]:
        rows = (
            self._db.query(DailySummaryORM)
            .filter(DailySummaryORM.entity_id == str(entity_id))
            .order_by(DailySummaryORM.summary_date.desc())
            .limit(limit)
            .all()
        )
        return [r.to_domain() for r in rows]
