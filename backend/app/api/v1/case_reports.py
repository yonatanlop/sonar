"""
Reporte de Seguimiento a caso.

- GET /case-reports/summary?month=YYYY-MM → JSON con la distribución geográfica de
  las cuentas (por ciudad de origen) y las cuentas / publicaciones cerradas en el mes.
- GET /case-reports/pdf?month=YYYY-MM → el mismo reporte en PDF (WeasyPrint).
"""
import io
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_case_manager
from app.database import get_db
from app.models.case import Case, CaseAccount, CaseRecord
from app.models.user import User

router = APIRouter(prefix="/case-reports", tags=["Seguimiento a caso"])

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_MONTHS_ES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _month_range(month: str) -> tuple[datetime, datetime, str]:
    """'YYYY-MM' → (inicio, fin_exclusivo, etiqueta 'Agosto 2026'). UTC."""
    if not month:
        now = datetime.now(timezone.utc)
        year, mon = now.year, now.month
    else:
        if not _MONTH_RE.match(month):
            raise HTTPException(status_code=422, detail="Mes inválido. Formato esperado: YYYY-MM")
        year, mon = int(month[:4]), int(month[5:7])
    start = datetime(year, mon, 1, tzinfo=timezone.utc)
    end = datetime(year + (mon == 12), (mon % 12) + 1, 1, tzinfo=timezone.utc)
    return start, end, f"{_MONTHS_ES[mon]} {year}"


def _build_summary(db: Session, month: str) -> dict:
    start, end, label = _month_range(month)

    # Distribución geográfica: cuentas por ciudad de origen
    city_col = func.trim(CaseAccount.city)
    geo_rows = (
        db.query(city_col.label("city"), func.count().label("cnt"))
        .filter(CaseAccount.city.isnot(None), city_col != "")
        .group_by(city_col)
        .order_by(func.count().desc(), city_col.asc())
        .all()
    )
    geo = [{"city": c, "count": n} for c, n in geo_rows]

    total_accounts = db.query(func.count(CaseAccount.id)).scalar() or 0
    accounts_with_city = sum(g["count"] for g in geo)

    # Cuentas cerradas en el mes
    acc_rows = (
        db.query(CaseAccount, Case.name)
        .join(Case, Case.id == CaseAccount.case_id)
        .filter(
            CaseAccount.account_removed.is_(True),
            CaseAccount.removed_date >= start,
            CaseAccount.removed_date < end,
        )
        .order_by(CaseAccount.removed_date.asc())
        .all()
    )
    accounts_closed = [{
        "case": name, "medium": a.medium, "author": a.author, "user_id": a.user_id,
        "city": a.city, "removed_date": a.removed_date.isoformat() if a.removed_date else None,
    } for a, name in acc_rows]

    # Publicaciones cerradas en el mes
    post_rows = (
        db.query(CaseRecord, CaseAccount.medium, CaseAccount.author, Case.name)
        .join(CaseAccount, CaseAccount.id == CaseRecord.account_id)
        .join(Case, Case.id == CaseRecord.case_id)
        .filter(
            CaseRecord.post_removed.is_(True),
            CaseRecord.post_removed_date >= start,
            CaseRecord.post_removed_date < end,
        )
        .order_by(CaseRecord.post_removed_date.asc())
        .all()
    )
    posts_closed = [{
        "post_id": r.post_id, "case": name, "medium": medium, "author": author,
        "affects": r.affects, "publication_url": r.publication_url,
        "removed_date": r.post_removed_date.isoformat() if r.post_removed_date else None,
    } for r, medium, author, name in post_rows]

    return {
        "month": start.strftime("%Y-%m"),
        "month_label": label,
        "totals": {
            "accounts": total_accounts,
            "accounts_with_city": accounts_with_city,
            "cities": len(geo),
            "accounts_closed": len(accounts_closed),
            "posts_closed": len(posts_closed),
        },
        "geo": geo,
        "accounts_closed": accounts_closed,
        "posts_closed": posts_closed,
    }


@router.get("/summary")
def case_report_summary(
    month: str = Query("", description="YYYY-MM (por defecto, el mes actual)"),
    db: Session = Depends(get_db),
    _:  User    = Depends(require_case_manager),
):
    return _build_summary(db, month)


@router.get("/pdf")
def case_report_pdf(
    month: str = Query("", description="YYYY-MM (por defecto, el mes actual)"),
    db: Session = Depends(get_db),
    _:  User    = Depends(require_case_manager),
):
    data = _build_summary(db, month)
    from app.reports.case_report import render_case_report_pdf
    pdf_bytes = render_case_report_pdf(data)
    filename = f"reporte_seguimiento_{data['month']}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
