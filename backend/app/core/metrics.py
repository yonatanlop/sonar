"""
Criterios de medición compartidos (Dashboard, Comparar alertas, motor de alertas y detección
de anomalías). Definirlos aquí evita que cada pantalla cuente "a su manera":

  · Menciones      → solo las relevantes a las keywords parametrizadas (`is_relevant`).
  · % negativo     → sobre las menciones CLASIFICADAS (con sentimiento), no sobre todas.
  · Bots           → cuentas DISTINTAS con puntaje >= BOT_THRESHOLD (no filas ni menciones).
  · Urgencia media → solo menciones ya procesadas por el NLP (las pendientes traen 0 por defecto).
  · Fechas         → día calendario de Colombia (ver app/core/timezone.py).
"""
from sqlalchemy import and_, func

from app.core.config import settings
from app.models.bot import AccountProfile
from app.models.mention import Mention

NEGATIVE_LABELS = ("negative", "very_negative")


def relevant():
    """Condición: la mención coincide con las keywords parametrizadas de su entidad."""
    return Mention.is_relevant == True  # noqa: E712


def negative():
    """Condición: mención negativa o muy negativa."""
    return Mention.sentiment_label.in_(NEGATIVE_LABELS)


def classified():
    """Condición: mención con sentimiento (las de baja confianza quedan con etiqueta NULL)."""
    return Mention.sentiment_label.isnot(None)


def authors_join(query):
    """Une menciones con el perfil de su autor (plataforma + id externo)."""
    return query.select_from(Mention).join(
        AccountProfile,
        and_(AccountProfile.platform_id == Mention.platform_id,
             AccountProfile.external_user_id == Mention.author_ext_id),
    )


def bot_authors_count(db, *conditions) -> int:
    """Cuentas DISTINTAS con puntaje de bot >= BOT_THRESHOLD entre las menciones que cumplen
    `conditions` (fechas, entidad, relevancia…)."""
    q = authors_join(db.query(func.count(func.distinct(AccountProfile.id)))).filter(
        *conditions,
        AccountProfile.bot_probability >= settings.BOT_THRESHOLD,
    )
    return q.scalar() or 0


def negative_pct(negative_count: int, classified_count: int) -> float:
    """% negativo sobre menciones clasificadas (0 si no hay ninguna)."""
    return round(negative_count / classified_count * 100, 1) if classified_count else 0
