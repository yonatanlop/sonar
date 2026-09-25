"""
Utilidades de hora de Colombia (America/Bogotá, UTC-5 fijo; el país no usa horario de verano).

El producto se usa en Colombia: "hoy", "últimos 7 días" y los filtros por fecha deben contarse por
día calendario colombiano, no por día UTC (que arranca a las 7:00 p. m. del día anterior).
"""
from datetime import datetime, timedelta, timezone

CO_TZ = timezone(timedelta(hours=-5))


def co_midnight(days_ago: int = 0) -> datetime:
    """Medianoche (00:00, hora de Colombia) de hoy o de hace `days_ago` días. Con zona horaria."""
    now = datetime.now(CO_TZ)
    return now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)


def co_date_start(value: str):
    """'YYYY-MM-DD' → medianoche de ese día en Colombia. Otro formato (ISO con hora) se devuelve igual."""
    if value and len(value) == 10:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=CO_TZ)
    return value


def co_date_end(value: str):
    """'YYYY-MM-DD' → 23:59:59 de ese día en Colombia. Otro formato conserva el comportamiento anterior."""
    if value and len(value) == 10:
        return datetime.strptime(value, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=CO_TZ)
    return value + "T23:59:59"
