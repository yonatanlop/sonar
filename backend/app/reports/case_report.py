"""
PDF del Reporte de Seguimiento a caso.

Reutiliza el motor de generator.py (Jinja2 + WeasyPrint + Matplotlib): dibuja un
gráfico de barras con las ciudades de origen y arma las tablas de cuentas y
publicaciones cerradas en el mes.
"""
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from weasyprint import HTML

from app.reports.generator import TEMPLATES_DIR, fig_to_b64, jinja_env


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def _cities_chart(geo: list[dict], top: int = 15) -> str | None:
    rows = [g for g in geo if g.get("count")][:top]
    if not rows:
        return None
    rows = list(reversed(rows))                      # mayor arriba
    labels = [g["city"] for g in rows]
    values = [g["count"] for g in rows]
    fig, ax = plt.subplots(figsize=(6.2, max(2.2, 0.42 * len(rows))))
    ax.barh(labels, values, color="#1d4ed8")
    ax.set_xlabel("Cuentas")
    for i, v in enumerate(values):
        ax.text(v, i, f" {v}", va="center", fontsize=9, color="#1f2937")
    ax.spines[["top", "right"]].set_visible(False)
    ax.margins(x=0.12)
    fig.tight_layout()
    return fig_to_b64(fig)


def render_case_report_pdf(data: dict) -> bytes:
    context = {
        **data,
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "cities_chart": _cities_chart(data.get("geo", [])),
        "accounts_closed": [{**a, "removed_date": _fmt_date(a.get("removed_date"))} for a in data.get("accounts_closed", [])],
        "posts_closed":    [{**p, "removed_date": _fmt_date(p.get("removed_date"))} for p in data.get("posts_closed", [])],
    }
    html_str = jinja_env.get_template("case_report.html").render(**context)
    return HTML(string=html_str, base_url=str(TEMPLATES_DIR)).write_pdf()
