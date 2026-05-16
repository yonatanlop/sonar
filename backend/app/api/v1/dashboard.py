from datetime import date, datetime, timedelta, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.entity import Entity
from app.models.mention import Mention, SocialPlatform
from app.models.alert import Alert
from app.models.bot import AccountProfile, BotAnalysis

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _delta(current: float, previous: float) -> dict:
    """Calcula variación porcentual entre dos períodos."""
    if previous == 0:
        pct = 100.0 if current > 0 else 0.0
    else:
        pct = round((current - previous) / previous * 100, 1)
    trend = "up" if pct > 1 else ("down" if pct < -1 else "stable")
    return {"value": current, "prev_value": previous, "delta_pct": pct, "trend": trend}


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

    # ── Comparativo período anterior (últimas 24h vs 24h previas) ─
    yesterday = today - timedelta(days=1)
    prev_total = db.query(func.count(Mention.id)).filter(
        Mention.collected_at >= yesterday,
        Mention.collected_at < today,
    ).scalar() or 0

    prev_negative_cnt = db.query(func.count(Mention.id)).filter(
        Mention.collected_at >= yesterday,
        Mention.collected_at < today,
        Mention.sentiment_label.in_(["negative", "very_negative"])
    ).scalar() or 0
    prev_negative_pct = round((prev_negative_cnt / prev_total * 100), 1) if prev_total else 0

    prev_bots = db.query(func.count(BotAnalysis.id)).filter(
        BotAnalysis.analyzed_at >= yesterday,
        BotAnalysis.analyzed_at < today,
        BotAnalysis.classification == "bot"
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

    top_entities = [{"entity_id": str(r.id), "name": r.name, "negative_count": r.negative_count} for r in top_rows]

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
            "today_mentions":  _delta(today_total,    prev_total),
            "negative_pct":    _delta(negative_pct,   prev_negative_pct),
            "bots_today":      _delta(bots_today,     prev_bots),
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


# ── Share of Voice ────────────────────────────────────────────

@router.get("/share-of-voice")
def share_of_voice(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Porcentaje de menciones por entidad sobre el total del período.
    Métrica clave de visibilidad: qué entidades dominan la conversación.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        db.query(Entity.id, Entity.name, func.count(Mention.id).label("cnt"))
        .join(Mention, Mention.entity_id == Entity.id)
        .filter(Mention.collected_at >= since, Entity.active == True)
        .group_by(Entity.id, Entity.name)
        .order_by(func.count(Mention.id).desc())
        .all()
    )

    total = sum(r.cnt for r in rows) or 1
    return {
        "days":  days,
        "total": total,
        "items": [
            {
                "entity_id":     str(r.id),
                "entity_name":   r.name,
                "mention_count": r.cnt,
                "pct":           round(r.cnt / total * 100, 1),
            }
            for r in rows
        ],
    }


# ── Distribución geográfica ───────────────────────────────────

# Mapa ISO-2 → nombre en español (países más frecuentes en LATAM + globales)
_CC_NAMES = {
    "CO": "Colombia",   "MX": "México",     "AR": "Argentina",  "PE": "Perú",
    "VE": "Venezuela",  "CL": "Chile",      "EC": "Ecuador",    "BO": "Bolivia",
    "PY": "Paraguay",   "UY": "Uruguay",    "CR": "Costa Rica", "PA": "Panamá",
    "DO": "Rep. Dominicana", "GT": "Guatemala", "HN": "Honduras", "SV": "El Salvador",
    "NI": "Nicaragua",  "CU": "Cuba",       "PR": "Puerto Rico",
    "US": "Estados Unidos", "ES": "España", "BR": "Brasil",     "GB": "Reino Unido",
    "DE": "Alemania",   "FR": "Francia",    "IT": "Italia",     "CA": "Canadá",
    "AU": "Australia",  "MX": "México",
}


@router.get("/geo-distribution")
def geo_distribution(
    days:      int                    = Query(7, ge=1, le=90),
    entity_id: Optional[str]          = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Distribución de menciones por país con sentimiento promedio.
    Solo incluye menciones con country_code NOT NULL (llenado por geocode_mentions).
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        db.query(
            Mention.country_code,
            func.count(Mention.id).label("cnt"),
            func.avg(Mention.sentiment_score).label("avg_sentiment"),
        )
        .filter(
            Mention.collected_at >= since,
            Mention.country_code.isnot(None),
        )
    )

    if entity_id:
        query = query.filter(Mention.entity_id == entity_id)

    rows = query.group_by(Mention.country_code).order_by(func.count(Mention.id).desc()).all()

    total = sum(r.cnt for r in rows) or 1

    return {
        "days":  days,
        "total": total,
        "items": [
            {
                "country_code":  r.country_code,
                "country_name":  _CC_NAMES.get(r.country_code, r.country_code),
                "mention_count": r.cnt,
                "pct":           round(r.cnt / total * 100, 1),
                "avg_sentiment": round(float(r.avg_sentiment), 3) if r.avg_sentiment else None,
            }
            for r in rows
        ],
    }


# ── Comparativo de entidades ──────────────────────────────────

@router.get("/compare")
def compare_entities(
    entity_ids: str    = Query(..., description="IDs separados por coma (máx 4)"),
    days:       int    = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Compara métricas de 2-4 entidades en el período: volumen, % negativo,
    bots, urgencia promedio y plataforma dominante.
    """
    ids = [i.strip() for i in entity_ids.split(",") if i.strip()][:4]
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = []

    for eid in ids:
        entity = db.query(Entity).filter(Entity.id == eid).first()
        if not entity:
            continue

        rows = db.query(
            Mention.sentiment_label,
            func.count(Mention.id).label("cnt"),
        ).filter(
            Mention.entity_id    == eid,
            Mention.collected_at >= since,
        ).group_by(Mention.sentiment_label).all()

        counts   = {r.sentiment_label: r.cnt for r in rows}
        total    = sum(counts.values())
        neg_cnt  = counts.get("negative", 0) + counts.get("very_negative", 0)
        neg_pct  = round(neg_cnt / total * 100, 1) if total else 0

        avg_urgency = db.query(func.avg(Mention.urgency_score)).filter(
            Mention.entity_id    == eid,
            Mention.collected_at >= since,
        ).scalar() or 0

        bot_count = db.query(func.count(AccountProfile.id)).join(
            Mention, Mention.author_ext_id == AccountProfile.external_user_id
        ).filter(
            Mention.entity_id    == eid,
            Mention.collected_at >= since,
            AccountProfile.bot_probability >= 0.7,
        ).scalar() or 0

        # Plataforma dominante
        plat_row = (
            db.query(SocialPlatform.code, func.count(Mention.id).label("cnt"))
            .join(Mention, Mention.platform_id == SocialPlatform.id)
            .filter(Mention.entity_id == eid, Mention.collected_at >= since)
            .group_by(SocialPlatform.code)
            .order_by(func.count(Mention.id).desc())
            .first()
        )

        result.append({
            "entity_id":      str(entity.id),
            "entity_name":    entity.name,
            "total_mentions": total,
            "negative_pct":   neg_pct,
            "bot_count":      bot_count,
            "avg_urgency":    round(float(avg_urgency), 1),
            "top_platform":   plat_row.code if plat_row else None,
            "sentiment":      counts,
        })

    return {"days": days, "entities": result}
