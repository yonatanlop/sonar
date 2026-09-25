"""
PDF del Balance de denuncias (Rizoma).

Reutiliza el motor de generator.py (Jinja2 + WeasyPrint + Matplotlib): gráfica de barras por
período (día / semana / mes), tabla por período y tabla por tipo de red.
"""
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from weasyprint import HTML

from app.core.timezone import CO_TZ
from app.reports.generator import TEMPLATES_DIR, fig_to_b64, jinja_env

_MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
_GRAN_ES = {"day": "día", "week": "semana", "month": "mes"}


def _label(start: str, granularity: str) -> str:
    """'AAAA-MM-DD' (inicio del período) → etiqueta corta."""
    y, m, d = start.split("-")
    if granularity == "month":
        return f"{_MONTHS[int(m) - 1]} {y}"
    if granularity == "week":
        return f"Sem {d}/{m}"
    return f"{d}/{m}"


def _fmt_day(iso_day: str) -> str:
    return "/".join(reversed(iso_day.split("-")))


def _chart(points: list[dict], granularity: str, show_groups: bool) -> str | None:
    if not points or not any(p["reported"] or p["posts_removed"] or p["accounts_closed"] or p["groups_closed"] for p in points):
        return None
    series = [
        ("Denuncias", "reported", "#f59e0b"),
        ("Publicaciones eliminadas", "posts_removed", "#10b981"),
        ("Cuentas cerradas", "accounts_closed", "#ef4444"),
    ]
    if show_groups:
        series.append(("Grupos cerrados", "groups_closed", "#6366f1"))

    labels = [_label(p["start"], granularity) for p in points]
    n, k = len(points), len(series)
    width = 0.8 / k
    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    for i, (name, key, color) in enumerate(series):
        xs = [x + (i - (k - 1) / 2) * width for x in range(n)]
        ax.bar(xs, [p[key] for p in points], width=width, label=name, color=color)
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, rotation=45 if n > 8 else 0, ha="right" if n > 8 else "center", fontsize=7)
    ax.yaxis.get_major_locator().set_params(integer=True)
    ax.tick_params(axis="y", labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=7, frameon=False, ncol=k, loc="upper center", bbox_to_anchor=(0.5, 1.14))
    fig.tight_layout()
    return fig_to_b64(fig)


def render_balance_pdf(data: dict) -> bytes:
    gran = data["granularity"]
    medium = data.get("medium")
    show_groups = medium in (None, "", "Facebook")
    points = [{**p, "label": _label(p["start"], gran)} for p in data["points"]]
    context = {
        **data,
        "points": points,
        "period_word": _GRAN_ES[gran],
        "date_from_fmt": _fmt_day(data["date_from"]),
        "date_to_fmt": _fmt_day(data["date_to"]),
        "show_groups": show_groups,
        "chart": _chart(data["points"], gran, show_groups),
        "generated_at": datetime.now(CO_TZ).strftime("%d/%m/%Y %H:%M"),
        "undated_total": sum(data["undated"].values()),
    }
    html_str = jinja_env.get_template("balance_report.html").render(**context)
    return HTML(string=html_str, base_url=str(TEMPLATES_DIR)).write_pdf()
