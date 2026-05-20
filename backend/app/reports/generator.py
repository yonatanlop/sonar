"""
Generador de reportes PDF con WeasyPrint + Jinja2 + Matplotlib.
Cada tipo de reporte tiene su propia función y plantilla HTML.
"""
import base64
import io
import os
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

TEMPLATES_DIR = Path(__file__).parent / "templates"
STORAGE_DIR   = Path("/app/storage/reports")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


def fig_to_b64(fig) -> str:
    """Convierte figura matplotlib a PNG base64 para embeber en HTML."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    buf.seek(0)
    plt.close(fig)
    return base64.b64encode(buf.read()).decode("utf-8")


def make_sentiment_pie(sentiment: dict) -> str:
    labels = ["Muy negativo", "Negativo", "Neutral", "Positivo"]
    values = [
        sentiment.get("very_negative", 0),
        sentiment.get("negative", 0),
        sentiment.get("neutral", 0),
        sentiment.get("positive", 0),
    ]
    colors = ["#dc2626", "#f97316", "#9ca3af", "#22c55e"]
    # Excluir etiquetas con valor 0
    filtered = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
    if not filtered:
        return ""
    labels, values, colors = zip(*filtered)

    fig, ax = plt.subplots(figsize=(5, 4))
    ax.pie(values, labels=labels, colors=colors, autopct="%1.1f%%",
           startangle=90, textprops={"fontsize": 9})
    ax.set_title("Distribución de Sentimiento", fontsize=11, fontweight="bold")
    return fig_to_b64(fig)


def make_timeline_bar(dates: list, negative: list, neutral: list, positive: list) -> str:
    fig, ax = plt.subplots(figsize=(10, 4))
    x = range(len(dates))
    ax.bar(x, negative, label="Negativo", color="#ef4444")
    ax.bar(x, neutral,  label="Neutral",  color="#d1d5db", bottom=negative)
    pos_bottom = [n + nu for n, nu in zip(negative, neutral)]
    ax.bar(x, positive, label="Positivo", color="#22c55e", bottom=pos_bottom)
    ax.set_xticks(list(x))
    ax.set_xticklabels(dates, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Menciones", fontsize=9)
    ax.set_title("Menciones por Día", fontsize=11, fontweight="bold")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig_to_b64(fig)


def make_tiers_chart(tier_data: list) -> str:
    visible = [t for t in tier_data if t['tier'] != 'Sin datos' and t['count'] > 0]
    if not visible:
        return ""
    names  = [t['tier']  for t in visible]
    counts = [t['count'] for t in visible]
    fig, ax = plt.subplots(figsize=(8, 3.5))
    bars = ax.barh(names, counts, color='#6366f1')
    ax.bar_label(bars, padding=4, fontsize=8)
    ax.set_xlabel('Menciones', fontsize=9)
    ax.set_title('Distribución por Nivel de Audiencia', fontsize=11, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)
    fig.tight_layout()
    return fig_to_b64(fig)


def make_platforms_bar(platforms: list) -> str:
    if not platforms:
        return ""
    names  = [p["name"]  for p in platforms]
    counts = [p["count"] for p in platforms]
    fig, ax = plt.subplots(figsize=(6, 3))
    bars = ax.barh(names, counts, color="#3b82f6")
    ax.bar_label(bars, padding=4, fontsize=8)
    ax.set_xlabel("Menciones", fontsize=9)
    ax.set_title("Menciones por Plataforma", fontsize=11, fontweight="bold")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    return fig_to_b64(fig)


# ── Generador principal ───────────────────────────────────────

def generate_report(report, db) -> str:
    """Genera el PDF según el tipo de reporte y retorna la ruta del archivo."""
    dispatch = {
        "entity":   _generate_entity,
        "country":  _generate_country,
        "bots":     _generate_bots,
        "alerts":   _generate_alerts,
    }
    generator_fn = dispatch.get(report.report_type, _generate_entity)
    return generator_fn(report, db)


def _generate_ai_narrative(entity_name: str, stats: dict, top_mentions: list) -> dict | None:
    """Genera narrativa ejecutiva con Groq. Retorna {text, model} o None si no hay API key."""
    try:
        from app.core.config import settings
        if not settings.GROQ_API_KEY:
            return None

        import groq

        sample_texts = []
        for m in top_mentions[:15]:
            label = (m.sentiment_label or "neutral").replace("_", " ")
            content = (m.content or "")[:200].replace("\n", " ")
            sample_texts.append(f"- [{label}] {content}")
        mentions_block = "\n".join(sample_texts) if sample_texts else "(sin menciones en el período)"

        prompt = (
            f"Eres un analista de reputación corporativa. "
            f"Redacta un análisis ejecutivo en español (3 párrafos, sin markdown) para el siguiente informe:\n\n"
            f"Entidad: {entity_name}\n"
            f"Total menciones: {stats['total']}\n"
            f"Menciones negativas: {stats['negative_pct']}%\n"
            f"Bots detectados: {stats['bot_count']}\n"
            f"Alertas generadas: {stats['alert_count']}\n\n"
            f"Menciones más impactantes:\n{mentions_block}\n\n"
            f"Estructura: (1) estado general de la reputación, "
            f"(2) principales focos de riesgo identificados, "
            f"(3) recomendación ejecutiva concreta. Sé directo y profesional."
        )

        client = groq.Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=settings.SUMMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        text = response.choices[0].message.content.strip()
        return {"text": text, "model": settings.SUMMARY_MODEL}
    except Exception:
        return None


def _render_to_pdf(template_name: str, context: dict, filename: str) -> str:
    template = jinja_env.get_template(template_name)
    html_str = template.render(**context)
    out_path = str(STORAGE_DIR / filename)
    HTML(string=html_str, base_url=str(TEMPLATES_DIR)).write_pdf(out_path)
    return out_path


def _get_sentiment_data(entity_id, date_from, date_to, db) -> dict:
    from sqlalchemy import func
    from app.models.mention import Mention
    rows = db.query(
        Mention.sentiment_label,
        func.count(Mention.id).label("cnt")
    ).filter(
        Mention.entity_id == entity_id,
        Mention.collected_at >= datetime.combine(date_from, datetime.min.time()),
        Mention.collected_at <= datetime.combine(date_to,   datetime.max.time()),
        Mention.sentiment_label.isnot(None),
    ).group_by(Mention.sentiment_label).all()
    return {r.sentiment_label: r.cnt for r in rows}


def _generate_entity(report, db) -> str:
    from sqlalchemy import func, case, and_
    from app.models.entity import Entity
    from app.models.mention import Mention, SocialPlatform
    from app.models.bot import BotAnalysis, AccountProfile
    from app.models.alert import Alert

    entity = db.query(Entity).filter(Entity.id == report.entity_id).first()
    if not entity:
        raise ValueError("Entidad no encontrada")

    date_from = report.date_from
    date_to   = report.date_to
    dt_from   = datetime.combine(date_from, datetime.min.time())
    dt_to     = datetime.combine(date_to,   datetime.max.time())

    # Estadísticas
    total = db.query(func.count(Mention.id)).filter(
        Mention.entity_id == entity.id,
        Mention.collected_at.between(dt_from, dt_to)
    ).scalar() or 0

    sentiment = _get_sentiment_data(entity.id, date_from, date_to, db)
    neg = sentiment.get("negative", 0) + sentiment.get("very_negative", 0)
    neg_pct = round(neg / total * 100, 1) if total else 0

    # Plataformas
    plat_rows = db.query(
        SocialPlatform.name,
        func.count(Mention.id).label("cnt")
    ).join(Mention, Mention.platform_id == SocialPlatform.id
    ).filter(
        Mention.entity_id == entity.id,
        Mention.collected_at.between(dt_from, dt_to)
    ).group_by(SocialPlatform.name).all()
    platforms = [{"name": r.name, "count": r.cnt} for r in plat_rows]

    # Top menciones por alcance
    top_mentions = db.query(Mention).filter(
        Mention.entity_id == entity.id,
        Mention.collected_at.between(dt_from, dt_to),
        Mention.sentiment_label.in_(["negative", "very_negative"]),
    ).order_by(Mention.reach.desc()).limit(10).all()

    # Alertas del período
    alerts = db.query(Alert).filter(
        Alert.entity_id == entity.id,
        Alert.triggered_at.between(dt_from, dt_to),
    ).order_by(Alert.triggered_at.desc()).all()

    # Bots
    bot_count = db.query(func.count(BotAnalysis.id)).filter(
        BotAnalysis.classification == "bot",
        BotAnalysis.analyzed_at.between(dt_from, dt_to),
    ).scalar() or 0

    # Distribución por tier de audiencia (outerjoin Mention ↔ AccountProfile)
    TIER_ORDER = ['Micro (0–500)', 'Pequeña (500–3K)', 'Media (3K–10K)',
                  'Macro (10K–30K)', 'Masiva (30K+)', 'Sin datos']
    tier_expr = case(
        (AccountProfile.followers_count == None, 'Sin datos'),
        (AccountProfile.followers_count < 500,   'Micro (0–500)'),
        (AccountProfile.followers_count < 3000,  'Pequeña (500–3K)'),
        (AccountProfile.followers_count < 10000, 'Media (3K–10K)'),
        (AccountProfile.followers_count < 30000, 'Macro (10K–30K)'),
        else_='Masiva (30K+)',
    )
    tier_rows = (
        db.query(
            tier_expr.label('tier'),
            func.count(Mention.id).label('count'),
            func.coalesce(func.sum(Mention.reach), 0).label('reach'),
        )
        .outerjoin(AccountProfile, and_(
            AccountProfile.platform_id      == Mention.platform_id,
            AccountProfile.external_user_id == Mention.author_ext_id,
        ))
        .filter(Mention.entity_id == entity.id,
                Mention.collected_at.between(dt_from, dt_to))
        .group_by(tier_expr)
        .all()
    )
    tier_data = sorted(
        [{'tier': r.tier, 'count': r.count, 'reach': int(r.reach)} for r in tier_rows],
        key=lambda x: TIER_ORDER.index(x['tier']) if x['tier'] in TIER_ORDER else 99,
    )

    # Menciones de cuentas verificadas
    verified_count = (
        db.query(func.count(Mention.id))
        .join(AccountProfile, and_(
            AccountProfile.platform_id      == Mention.platform_id,
            AccountProfile.external_user_id == Mention.author_ext_id,
        ))
        .filter(Mention.entity_id == entity.id,
                Mention.collected_at.between(dt_from, dt_to),
                AccountProfile.verified == True)
        .scalar() or 0
    )

    # Top influencers (cuentas con ≥3K seguidores)
    top_influencer_rows = (
        db.query(
            Mention.author_username,
            AccountProfile.followers_count,
            AccountProfile.verified,
            func.count(Mention.id).label('mention_count'),
            func.coalesce(func.sum(Mention.reach), 0).label('total_reach'),
        )
        .join(AccountProfile, and_(
            AccountProfile.platform_id      == Mention.platform_id,
            AccountProfile.external_user_id == Mention.author_ext_id,
        ))
        .filter(Mention.entity_id == entity.id,
                Mention.collected_at.between(dt_from, dt_to),
                AccountProfile.followers_count >= 3000)
        .group_by(Mention.author_username, AccountProfile.followers_count, AccountProfile.verified)
        .order_by(AccountProfile.followers_count.desc())
        .limit(15)
        .all()
    )
    top_influencers = [
        {'username': r.author_username, 'followers': r.followers_count or 0,
         'verified': bool(r.verified), 'mention_count': r.mention_count,
         'total_reach': int(r.total_reach)}
        for r in top_influencer_rows
    ]

    # Risk score (simple)
    risk_score = min(100, int(neg_pct * 0.7 + (bot_count / max(total, 1) * 100) * 0.3))
    risk_label = "ALTO" if risk_score >= 66 else "MEDIO" if risk_score >= 36 else "BAJO"
    risk_color = "#dc2626" if risk_score >= 66 else "#d97706" if risk_score >= 36 else "#16a34a"

    # Gráficas
    chart_sentiment = make_sentiment_pie(sentiment)
    chart_platforms = make_platforms_bar(platforms)
    chart_tiers     = make_tiers_chart(tier_data)

    # Narrativa IA
    ai_narrative = _generate_ai_narrative(
        entity.name,
        {"total": total, "negative_pct": neg_pct, "bot_count": bot_count, "alert_count": len(alerts)},
        top_mentions,
    )

    context = {
        "entity": entity,
        "report": report,
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "stats": {
            "total": total, "negative_pct": neg_pct,
            "bot_count": bot_count, "alert_count": len(alerts),
        },
        "risk_score": risk_score, "risk_label": risk_label, "risk_color": risk_color,
        "sentiment": sentiment,
        "platforms": platforms,
        "top_mentions": top_mentions,
        "alerts": alerts,
        "chart_sentiment": chart_sentiment,
        "chart_platforms": chart_platforms,
        "chart_tiers":     chart_tiers,
        "tier_data":       tier_data,
        "verified_count":  verified_count,
        "top_influencers": top_influencers,
        "ai_narrative":    ai_narrative,
    }

    filename = f"entidad_{entity.id}_{date_from}_{date_to}.pdf"
    return _render_to_pdf("entity_report.html", context, filename)


def _generate_alerts(report, db) -> str:
    from sqlalchemy import func
    from app.models.alert import Alert
    from app.models.entity import Entity

    dt_from = datetime.combine(report.date_from, datetime.min.time())
    dt_to   = datetime.combine(report.date_to,   datetime.max.time())

    alerts = db.query(Alert).filter(
        Alert.triggered_at.between(dt_from, dt_to)
    ).order_by(Alert.triggered_at.desc()).all()

    totals = {sev: sum(1 for a in alerts if a.severity == sev)
              for sev in ["critical", "high", "medium", "low"]}

    context = {
        "report":       report,
        "alerts":       alerts,
        "totals":       totals,
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "db":           db,
    }
    filename = f"alertas_{report.date_from}_{report.date_to}.pdf"
    return _render_to_pdf("alerts_report.html", context, filename)


def _generate_country(report, db) -> str:
    # Implementación similar a entity pero agrupada por país
    filename = f"pais_{report.country_code}_{report.date_from}_{report.date_to}.pdf"
    context = {"report": report, "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M")}
    return _render_to_pdf("country_report.html", context, filename)


def _generate_bots(report, db) -> str:
    filename = f"bots_{report.date_from}_{report.date_to}.pdf"
    context = {"report": report, "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M")}
    return _render_to_pdf("bots_report.html", context, filename)
