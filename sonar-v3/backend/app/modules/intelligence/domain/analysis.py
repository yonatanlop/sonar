from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass
class Anomaly:
    id: UUID
    entity_id: UUID
    detected_at: datetime
    metric: str
    z_score: float
    value: float
    baseline: float
    std_dev: float
    context_explanation: str | None


@dataclass
class TrendForecast:
    id: UUID
    entity_id: UUID
    forecast_date: date
    predicted_count: float
    confidence_low: float
    confidence_high: float
    model_used: str
    generated_at: datetime


@dataclass
class DailySummary:
    id: UUID
    entity_id: UUID
    summary_date: date
    summary_text: str
    model_used: str
    mention_count: int
    generated_at: datetime
