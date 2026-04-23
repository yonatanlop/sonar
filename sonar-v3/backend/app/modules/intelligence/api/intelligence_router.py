from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.shared.deps import get_db, get_current_user
from app.modules.intelligence.infrastructure.orm import AnomalyORM, TrendForecastORM, DailySummaryORM

router = APIRouter(prefix="/intelligence", tags=["Inteligencia"])


class AnomalyOut(BaseModel):
    id: UUID
    entity_id: UUID
    detected_at: datetime
    metric: str
    z_score: float
    value: float
    baseline: float
    context_explanation: str | None = None


class TrendForecastOut(BaseModel):
    id: UUID
    entity_id: UUID
    forecast_date: date
    predicted_count: float
    confidence_low: float
    confidence_high: float
    model_used: str


class DailySummaryOut(BaseModel):
    id: UUID
    entity_id: UUID
    summary_date: date
    summary_text: str
    model_used: str
    mention_count: int
    generated_at: datetime


@router.get("/anomalies", response_model=list[AnomalyOut])
def list_anomalies(
    entity_id: UUID | None = Query(None),
    hours: int = Query(24),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    q = db.query(AnomalyORM).filter(AnomalyORM.detected_at >= since)
    if entity_id:
        q = q.filter(AnomalyORM.entity_id == str(entity_id))
    rows = q.order_by(AnomalyORM.detected_at.desc()).all()
    return [AnomalyOut(
        id=r.id, entity_id=r.entity_id, detected_at=r.detected_at,
        metric=r.metric, z_score=r.z_score, value=r.value,
        baseline=r.baseline, context_explanation=r.context_explanation,
    ) for r in rows]


@router.get("/trends", response_model=list[TrendForecastOut])
def list_trends(
    entity_id: UUID = Query(...),
    from_date: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    rows = (
        db.query(TrendForecastORM)
        .filter(TrendForecastORM.entity_id == str(entity_id),
                TrendForecastORM.forecast_date >= from_date)
        .order_by(TrendForecastORM.forecast_date.asc())
        .all()
    )
    return [TrendForecastOut(
        id=r.id, entity_id=r.entity_id, forecast_date=r.forecast_date,
        predicted_count=r.predicted_count, confidence_low=r.confidence_low,
        confidence_high=r.confidence_high, model_used=r.model_used,
    ) for r in rows]


@router.get("/summaries", response_model=list[DailySummaryOut])
def list_summaries(
    entity_id: UUID = Query(...),
    limit: int = Query(30, le=90),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    rows = (
        db.query(DailySummaryORM)
        .filter(DailySummaryORM.entity_id == str(entity_id))
        .order_by(DailySummaryORM.summary_date.desc())
        .limit(limit)
        .all()
    )
    return [DailySummaryOut(
        id=r.id, entity_id=r.entity_id, summary_date=r.summary_date,
        summary_text=r.summary_text, model_used=r.model_used,
        mention_count=r.mention_count, generated_at=r.generated_at,
    ) for r in rows]
