from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.entity import Entity
from app.models.mention import Mention, SocialPlatform
from app.models.alert import Alert
from app.models.bot import AccountProfile, BotAnalysis

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("")
def get_dashboard(db: Session = Depends(get_db),
                  _=Depends(get_current_user)):
    now   = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # ── Métricas del día ──────────────────────────────────────
    today_total = db.query(func.count(Mention.id)).filter(
        Mention.collected_at >= today
    ).scalar() or 0

    today_negative = db.query(func.count(Mention.id)).filter(
        Mention.collected_at >= today,
        Mention.sentiment_label.in_(["negative", "very_negative"])
    ).scalar() or 0

    negative_pct = round((today_negative / today_total * 100), 1) if today_total else 0

    bots_today = db.query(func.count(BotAnalysis.id)).filter(
        BotAnalysis.analyzed_at >= today,
        BotAnalysis.classification == "bot"
    ).scalar() or 0

    active_entities = db.query(func.count(Entity.id)).filter(
        Entity.active == True
    ).scalar() or 0

    # ── Timeline: últimos 14 días ─────────────────────────────
    dates, neg_counts, neu_counts, pos_counts = [], [], [], []
    for i in range(13, -1, -1):
        day_start = (today - timedelta(days=i))
        day_end   = day_start + timedelta(days=1)

        rows = db.query(
            Mention.sentiment_label,
            func.count(Mention.id).label("cnt")
        ).filter(
            Mention.collected_at >= day_start,
            Mention.collected_at <  day_end,
        ).group_by(Mention.sentiment_label).all()

        counts = {r.sentiment_label: r.cnt for r in rows}
        dates.append(day_start.strftime("%d/%m"))
        neg_counts.append(counts.get("negative", 0) + counts.get("very_negative", 0))
        neu_counts.append(counts.get("neutral", 0))
        pos_counts.append(counts.get("positive", 0))

    # ── Distribución de sentimiento (últimos 7 días) ──────────
    since_7 = today - timedelta(days=7)
    sentiment_rows = db.query(
        Mention.sentiment_label,
        func.count(Mention.id).label("cnt")
    ).filter(
        Mention.collected_at >= since_7,
        Mention.sentiment_label.isnot(None)
    ).group_by(Mention.sentiment_label).all()

    sentiment = {r.sentiment_label: r.cnt for r in sentiment_rows}

    # ── Top 5 entidades con más menciones negativas (7 días) ──
    top_rows = db.query(
        Entity.id,
        Entity.name,
        func.count(Mention.id).label("negative_count")
    ).join(Mention, Mention.entity_id == Entity.id).filter(
        Mention.collected_at >= since_7,
        Mention.sentiment_label.in_(["negative", "very_negative"])
    ).group_by(Entity.id, Entity.name
    ).order_by(func.count(Mention.id).desc()
    ).limit(5).all()

    top_entities = [{"name": r.name, "negative_count": r.negative_count} for r in top_rows]

    # ── Alertas recientes (últimas 5) ─────────────────────────
    alert_rows = db.query(Alert).order_by(Alert.triggered_at.desc()).limit(5).all()
    recent_alerts = [
        {
            "id": str(a.id),
            "entity_name": db.query(Entity.name).filter(Entity.id == a.entity_id).scalar() or "—",
            "message": a.message,
            "severity": a.severity,
            "triggered_at": a.triggered_at.isoformat(),
            "acknowledged": a.acknowledged,
        }
        for a in alert_rows
    ]

    # ── Bots por plataforma (v2) ──────────────────────────────
    bot_rows = (
        db.query(
            SocialPlatform.name.label("platform_name"),
            SocialPlatform.code.label("platform_code"),
            func.count(AccountProfile.id).label("total"),
            func.sum(
                case((AccountProfile.bot_probability >= 0.7, 1), else_=0)
            ).label("bots"),
        )
        .join(AccountProfile, AccountProfile.platform_id == SocialPlatform.id)
        .filter(AccountProfile.bot_probability.isnot(None))
        .group_by(SocialPlatform.id, SocialPlatform.name, SocialPlatform.code)
        .all()
    )

    bots_by_platform = [
        {
            "platform":  r.platform_name,
            "code":      r.platform_code,
            "total":     r.total,
            "bots":      int(r.bots or 0),
            "bot_pct":   round(int(r.bots or 0) / max(r.total, 1) * 100, 1),
        }
        for r in bot_rows
        if r.total > 0
    ]

    return {
        "stats": {
            "today_mentions": today_total,
            "negative_pct": negative_pct,
            "bots_today": bots_today,
            "active_entities": active_entities,
        },
        "timeline": {
            "dates": dates,
            "negative": neg_counts,
            "neutral":  neu_counts,
            "positive": pos_counts,
        },
        "sentiment": {
            "very_negative": sentiment.get("very_negative", 0),
            "negative":      sentiment.get("negative",      0),
            "neutral":       sentiment.get("neutral",       0),
            "positive":      sentiment.get("positive",      0),
        },
        "top_entities":      top_entities,
        "recent_alerts":     recent_alerts,
        "bots_by_platform":  bots_by_platform,
    }
