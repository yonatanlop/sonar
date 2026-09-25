"""
Reporte de Seguimiento a caso.

- GET /case-reports/summary?month=YYYY-MM → JSON con la distribución geográfica de
  las cuentas (por ciudad de origen) y las cuentas / publicaciones cerradas en el mes.
- GET /case-reports/pdf?month=YYYY-MM → el mismo reporte en PDF (WeasyPrint).

Rizoma (balance e historial de cuentas de atacantes; fechas por día calendario de Colombia):
- GET /case-reports/balance   → denuncias / eliminaciones / cierres por día, semana o mes.
- GET /case-reports/closed    → cuentas y publicaciones cerradas en un rango, filtrables por red.
- GET /case-reports/accounts  → cuentas de atacantes con filtros (red, estado, búsqueda).
- GET /case-reports/accounts/{id}/history → línea de tiempo de una cuenta.
- GET /case-reports/events    → últimos eventos de todas las cuentas.
"""
import io
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import require_case_manager
from app.core.timezone import CO_TZ, co_date_end, co_date_start, co_midnight
from app.database import get_db
from app.models.case import Case, CaseAccount, CaseAccountEvent, CaseRecord
from app.models.facebook_group import FacebookGroup
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


# ══════════════════════════════════════════════════════════════
#  Rizoma — balance, cerradas, cuentas e historial
# ══════════════════════════════════════════════════════════════

MEDIUMS = ("X", "Facebook", "Instagram", "TikTok", "YouTube", "Threads", "Sitio Web")
EVENT_LABELS = {
    "account_created":     "Cuenta registrada",
    "post_added":          "Publicación registrada",
    "report_added":        "Publicación denunciada",
    "report_removed":      "Denuncia retirada",
    "post_removed":        "Publicación eliminada",
    "post_restored":       "Publicación restablecida",
    "account_closed":      "Cuenta cerrada",
    "account_reopened":    "Cuenta reabierta",
    "new_account_created": "Creó una cuenta nueva",
    "new_account_cleared": "Cuenta nueva descartada",
}
_BOGOTA = "America/Bogota"


def _check_medium(medium: Optional[str]) -> Optional[str]:
    if not medium:
        return None
    if medium not in MEDIUMS:
        raise HTTPException(status_code=422, detail=f"Red inválida. Opciones: {', '.join(MEDIUMS)}")
    return medium


def _resolve_range(date_from: str, date_to: str, granularity: str):
    """Rango [inicio, fin] en hora de Colombia. Por defecto: 30 días / 12 semanas / 12 meses."""
    try:
        end = co_date_end(date_to) if date_to else co_date_end(co_midnight().strftime("%Y-%m-%d"))
        if date_from:
            start = co_date_start(date_from)
        else:
            today = co_midnight()
            back = {"day": 29, "week": 7 * 11, "month": 365}[granularity]
            start = today - timedelta(days=back)
    except ValueError:
        raise HTTPException(status_code=422, detail="Fecha inválida. Formato esperado: AAAA-MM-DD")
    if isinstance(start, str) or isinstance(end, str):
        raise HTTPException(status_code=422, detail="Fecha inválida. Formato esperado: AAAA-MM-DD")
    if start > end:
        raise HTTPException(status_code=422, detail="La fecha inicial es posterior a la final")
    return start, end


def _bucket_col(col, granularity: str):
    return func.date_trunc(granularity, func.timezone(_BOGOTA, col))


def _bucket_starts(start: datetime, end: datetime, granularity: str) -> list[date]:
    """Inicios de cada período (día / lunes de la semana / día 1 del mes) entre start y end."""
    d0 = start.astimezone(CO_TZ).date()
    d1 = end.astimezone(CO_TZ).date()
    if granularity == "week":
        d0 -= timedelta(days=d0.weekday())
    elif granularity == "month":
        d0 = d0.replace(day=1)
    out, cur = [], d0
    while cur <= d1:
        out.append(cur)
        if granularity == "day":
            cur += timedelta(days=1)
        elif granularity == "week":
            cur += timedelta(days=7)
        else:
            cur = date(cur.year + (cur.month == 12), (cur.month % 12) + 1, 1)
    return out


@router.get("/balance")
def denuncias_balance(
    granularity: str = Query("week", pattern="^(day|week|month)$"),
    date_from: str = Query("", description="AAAA-MM-DD"),
    date_to:   str = Query("", description="AAAA-MM-DD"),
    medium:    str = Query("", description="Red social (X, Facebook, Instagram, TikTok, YouTube, …)"),
    db: Session = Depends(get_db),
    _:  User    = Depends(require_case_manager),
):
    """Balance de denuncias: por día, semana o mes, cuántas denuncias se hicieron y cuántas
    publicaciones / cuentas / grupos se cerraron. Los hechos sin fecha registrada se cuentan aparte."""
    medium = _check_medium(medium)
    start, end = _resolve_range(date_from, date_to, granularity)

    acc_f = [CaseAccount.medium == medium] if medium else []

    def rec_series(date_col, flag):
        b = _bucket_col(date_col, granularity)
        rows = (
            db.query(b.label("b"), func.count().label("n"))
            .select_from(CaseRecord).join(CaseAccount, CaseAccount.id == CaseRecord.account_id)
            .filter(flag.is_(True), date_col >= start, date_col <= end, *acc_f)
            .group_by(b).all()
        )
        return {r.b.date(): r.n for r in rows}

    reported  = rec_series(CaseRecord.reported_date, CaseRecord.reported)
    removed   = rec_series(CaseRecord.post_removed_date, CaseRecord.post_removed)

    b = _bucket_col(CaseAccount.removed_date, granularity)
    closed_rows = (
        db.query(b.label("b"), func.count().label("n"))
        .filter(CaseAccount.account_removed.is_(True), CaseAccount.removed_date >= start,
                CaseAccount.removed_date <= end, *acc_f)
        .group_by(b).all()
    )
    accounts_closed = {r.b.date(): r.n for r in closed_rows}

    include_groups = medium in (None, "Facebook")
    groups_started, groups_closed = {}, {}
    if include_groups:
        for col, target in ((FacebookGroup.start_date, groups_started), (FacebookGroup.end_date, groups_closed)):
            gb = _bucket_col(col, granularity)
            for r in (db.query(gb.label("b"), func.count().label("n"))
                      .filter(col >= start, col <= end).group_by(gb).all()):
                target[r.b.date()] = r.n

    points = []
    for d in _bucket_starts(start, end, granularity):
        points.append({
            "start":           d.isoformat(),
            "reported":        reported.get(d, 0),
            "posts_removed":   removed.get(d, 0),
            "accounts_closed": accounts_closed.get(d, 0),
            "groups_started":  groups_started.get(d, 0),
            "groups_closed":   groups_closed.get(d, 0),
        })

    # Hechos marcados como hechos pero sin fecha (históricos): no entran en la serie
    undated = {
        "reported": (db.query(func.count(CaseRecord.id)).join(CaseAccount, CaseAccount.id == CaseRecord.account_id)
                     .filter(CaseRecord.reported.is_(True), CaseRecord.reported_date.is_(None), *acc_f).scalar() or 0),
        "posts_removed": (db.query(func.count(CaseRecord.id)).join(CaseAccount, CaseAccount.id == CaseRecord.account_id)
                          .filter(CaseRecord.post_removed.is_(True), CaseRecord.post_removed_date.is_(None), *acc_f).scalar() or 0),
        "accounts_closed": (db.query(func.count(CaseAccount.id))
                            .filter(CaseAccount.account_removed.is_(True), CaseAccount.removed_date.is_(None), *acc_f).scalar() or 0),
    }

    # Acumulado histórico (todas las fechas): tasa de eliminación de lo denunciado
    rep_all = (db.query(func.count(CaseRecord.id)).join(CaseAccount, CaseAccount.id == CaseRecord.account_id)
               .filter(CaseRecord.reported.is_(True), *acc_f).scalar() or 0)
    rep_removed = (db.query(func.count(CaseRecord.id)).join(CaseAccount, CaseAccount.id == CaseRecord.account_id)
                   .filter(CaseRecord.reported.is_(True), CaseRecord.post_removed.is_(True), *acc_f).scalar() or 0)
    acc_all = db.query(func.count(CaseAccount.id)).filter(*acc_f).scalar() or 0
    acc_closed_all = db.query(func.count(CaseAccount.id)).filter(CaseAccount.account_removed.is_(True), *acc_f).scalar() or 0

    # Desglose por red dentro del rango
    by_medium = []
    for m in MEDIUMS:
        if medium and m != medium:
            continue
        rep_n = (db.query(func.count(CaseRecord.id)).join(CaseAccount, CaseAccount.id == CaseRecord.account_id)
                 .filter(CaseAccount.medium == m, CaseRecord.reported.is_(True),
                         CaseRecord.reported_date >= start, CaseRecord.reported_date <= end).scalar() or 0)
        rem_n = (db.query(func.count(CaseRecord.id)).join(CaseAccount, CaseAccount.id == CaseRecord.account_id)
                 .filter(CaseAccount.medium == m, CaseRecord.post_removed.is_(True),
                         CaseRecord.post_removed_date >= start, CaseRecord.post_removed_date <= end).scalar() or 0)
        clo_n = (db.query(func.count(CaseAccount.id))
                 .filter(CaseAccount.medium == m, CaseAccount.account_removed.is_(True),
                         CaseAccount.removed_date >= start, CaseAccount.removed_date <= end).scalar() or 0)
        tot_n = db.query(func.count(CaseAccount.id)).filter(CaseAccount.medium == m).scalar() or 0
        if rep_n or rem_n or clo_n or tot_n:
            by_medium.append({"medium": m, "reported": rep_n, "posts_removed": rem_n,
                              "accounts_closed": clo_n, "accounts": tot_n})

    totals = {k: sum(p[k] for p in points)
              for k in ("reported", "posts_removed", "accounts_closed", "groups_started", "groups_closed")}
    return {
        "granularity": granularity,
        "date_from":   start.astimezone(CO_TZ).strftime("%Y-%m-%d"),
        "date_to":     end.astimezone(CO_TZ).strftime("%Y-%m-%d"),
        "medium":      medium,
        "points":      points,
        "totals":      totals,
        "undated":     undated,
        "overall": {
            "reported": rep_all, "reported_removed": rep_removed,
            "removal_rate": round(rep_removed / rep_all * 100, 1) if rep_all else 0,
            "accounts": acc_all, "accounts_closed": acc_closed_all,
        },
        "by_medium": by_medium,
    }


@router.get("/closed")
def closed_items(
    date_from: str = Query("", description="AAAA-MM-DD (por defecto, hace 30 días)"),
    date_to:   str = Query("", description="AAAA-MM-DD (por defecto, hoy)"),
    medium:    str = Query(""),
    db: Session = Depends(get_db),
    _:  User    = Depends(require_case_manager),
):
    """Cuentas, publicaciones y grupos cerrados en el rango (hora de Colombia), filtrables por red."""
    medium = _check_medium(medium)
    start, end = _resolve_range(date_from, date_to, "day")

    acc_q = (db.query(CaseAccount, Case.name).join(Case, Case.id == CaseAccount.case_id)
             .filter(CaseAccount.account_removed.is_(True), CaseAccount.removed_date >= start, CaseAccount.removed_date <= end))
    if medium:
        acc_q = acc_q.filter(CaseAccount.medium == medium)
    accounts = [{
        "account_id": str(a.id), "case_id": str(a.case_id), "case": name, "medium": a.medium,
        "author": a.author, "user_id": a.user_id, "city": a.city,
        "removed_date": a.removed_date.isoformat(),
        "created_new_account": a.created_new_account,
    } for a, name in acc_q.order_by(CaseAccount.removed_date.desc()).all()]

    post_q = (db.query(CaseRecord, CaseAccount.medium, CaseAccount.author, Case.name)
              .join(CaseAccount, CaseAccount.id == CaseRecord.account_id).join(Case, Case.id == CaseRecord.case_id)
              .filter(CaseRecord.post_removed.is_(True), CaseRecord.post_removed_date >= start, CaseRecord.post_removed_date <= end))
    if medium:
        post_q = post_q.filter(CaseAccount.medium == medium)
    posts = [{
        "post_id": r.post_id, "account_id": str(r.account_id), "case_id": str(r.case_id), "case": name,
        "medium": m, "author": author, "affects": r.affects, "publication_url": r.publication_url,
        "reported_date": r.reported_date.isoformat() if r.reported_date else None,
        "removed_date": r.post_removed_date.isoformat(),
    } for r, m, author, name in post_q.order_by(CaseRecord.post_removed_date.desc()).all()]

    groups = []
    if medium in (None, "Facebook"):
        groups = [{
            "id": str(g.id), "group_url": g.group_url, "reason": g.reason,
            "start_date": g.start_date.isoformat(), "end_date": g.end_date.isoformat(),
        } for g in (db.query(FacebookGroup)
                    .filter(FacebookGroup.end_date >= start, FacebookGroup.end_date <= end)
                    .order_by(FacebookGroup.end_date.desc()).all())]

    # Cerradas sin fecha (históricas): se listan aparte para no perderlas
    undated_acc = db.query(func.count(CaseAccount.id)).filter(
        CaseAccount.account_removed.is_(True), CaseAccount.removed_date.is_(None),
        *([CaseAccount.medium == medium] if medium else [])).scalar() or 0
    undated_post = (db.query(func.count(CaseRecord.id)).join(CaseAccount, CaseAccount.id == CaseRecord.account_id)
                    .filter(CaseRecord.post_removed.is_(True), CaseRecord.post_removed_date.is_(None),
                            *([CaseAccount.medium == medium] if medium else [])).scalar() or 0)

    return {
        "date_from": start.astimezone(CO_TZ).strftime("%Y-%m-%d"),
        "date_to":   end.astimezone(CO_TZ).strftime("%Y-%m-%d"),
        "medium":    medium,
        "totals":    {"accounts": len(accounts), "posts": len(posts), "groups": len(groups)},
        "undated":   {"accounts": undated_acc, "posts": undated_post},
        "accounts":  accounts,
        "posts":     posts,
        "groups":    groups,
    }


_ACCOUNT_STATUS = {
    "activa": lambda: (CaseAccount.account_removed.isnot(True),),
    "cerrada": lambda: (CaseAccount.account_removed.is_(True),),
    "cuenta_nueva": lambda: (CaseAccount.created_new_account.is_(True),),
}
_ACCOUNTS_PAGE = 50


@router.get("/accounts")
def attacker_accounts(
    medium: str = Query(""),
    status: str = Query("", pattern="^(|activa|cerrada|cuenta_nueva)$"),
    q:      str = Query("", description="Busca en usuario, id, caso o ciudad"),
    page:   int = Query(1, ge=1),
    db: Session = Depends(get_db),
    _:  User    = Depends(require_case_manager),
):
    """Cuentas de atacantes (de todos los casos) con filtro por red, estado y búsqueda."""
    medium = _check_medium(medium)

    base_filters = []
    if status:
        base_filters += list(_ACCOUNT_STATUS[status]())
    if q.strip():
        like = f"%{q.strip()}%"
        base_filters.append(or_(CaseAccount.author.ilike(like), CaseAccount.user_id.ilike(like),
                                CaseAccount.city.ilike(like), Case.name.ilike(like)))

    # Conteos por red con los mismos filtros (menos la red), para los chips del filtro
    med_rows = (db.query(CaseAccount.medium, func.count(CaseAccount.id))
                .join(Case, Case.id == CaseAccount.case_id).filter(*base_filters)
                .group_by(CaseAccount.medium).all())
    medium_counts = {(m or "Sin red"): n for m, n in med_rows}

    rec = (db.query(
        CaseRecord.account_id.label("aid"),
        func.count().label("n"),
        func.count().filter(CaseRecord.reported.is_(True)).label("rep"),
        func.count().filter(CaseRecord.post_removed.is_(True)).label("rem"),
    ).group_by(CaseRecord.account_id).subquery())
    last_ev = (db.query(CaseAccountEvent.account_id.label("aid"),
                        func.max(func.coalesce(CaseAccountEvent.event_date, CaseAccountEvent.created_at)).label("last"))
               .group_by(CaseAccountEvent.account_id).subquery())

    query = (db.query(CaseAccount, Case.name, rec.c.n, rec.c.rep, rec.c.rem, last_ev.c.last)
             .join(Case, Case.id == CaseAccount.case_id)
             .outerjoin(rec, rec.c.aid == CaseAccount.id)
             .outerjoin(last_ev, last_ev.c.aid == CaseAccount.id)
             .filter(*base_filters))
    if medium:
        query = query.filter(CaseAccount.medium == medium)

    total = query.count()
    rows = (query.order_by(last_ev.c.last.desc().nullslast(), CaseAccount.created_at.desc())
            .offset((page - 1) * _ACCOUNTS_PAGE).limit(_ACCOUNTS_PAGE).all())
    items = [{
        "id": str(a.id), "case_id": str(a.case_id), "case": name, "medium": a.medium,
        "author": a.author, "user_id": a.user_id, "profile_url": a.profile_url, "city": a.city,
        "followers": a.followers, "verified": a.verified,
        "account_removed": a.account_removed is True,
        "removed_date": a.removed_date.isoformat() if a.removed_date else None,
        "created_new_account": a.created_new_account is True,
        "posts": n or 0, "reported": rep or 0, "posts_removed": rem or 0,
        "last_activity": last.isoformat() if last else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a, name, n, rep, rem, last in rows]

    return {
        "items": items, "total": total, "page": page,
        "pages": max(1, -(-total // _ACCOUNTS_PAGE)),
        "medium_counts": medium_counts,
    }


def _event_dict(e: CaseAccountEvent, user_name: Optional[str]) -> dict:
    return {
        "id": str(e.id), "type": e.event_type, "label": EVENT_LABELS.get(e.event_type, e.event_type),
        "event_date": e.event_date.isoformat() if e.event_date else None,
        "logged_at":  e.created_at.isoformat() if e.created_at else None,
        "detail": e.detail, "by": user_name,
    }


@router.get("/accounts/{account_id}/history")
def account_history(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    _:  User    = Depends(require_case_manager),
):
    """Línea de tiempo de una cuenta de atacante (más reciente primero; los hechos sin fecha al final)."""
    row = (db.query(CaseAccount, Case.name).join(Case, Case.id == CaseAccount.case_id)
           .filter(CaseAccount.id == account_id).first())
    if not row:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    a, case_name = row

    events = (db.query(CaseAccountEvent, User.full_name)
              .outerjoin(User, User.id == CaseAccountEvent.created_by)
              .filter(CaseAccountEvent.account_id == account_id).all())
    events.sort(key=lambda t: (t[0].event_date is None, -(t[0].event_date or t[0].created_at).timestamp()))

    posts = (db.query(CaseRecord).filter(CaseRecord.account_id == account_id)
             .order_by(CaseRecord.post_id.asc()).all())
    return {
        "account": {
            "id": str(a.id), "case_id": str(a.case_id), "case": case_name, "medium": a.medium,
            "author": a.author, "user_id": a.user_id, "profile_url": a.profile_url, "city": a.city,
            "account_removed": a.account_removed is True,
            "removed_date": a.removed_date.isoformat() if a.removed_date else None,
            "created_new_account": a.created_new_account is True, "new_account_info": a.new_account_info,
        },
        "events": [_event_dict(e, name) for e, name in events],
        "posts": [{
            "post_id": r.post_id, "publication_url": r.publication_url, "affects": r.affects,
            "reported": r.reported is True,
            "reported_date": r.reported_date.isoformat() if r.reported_date else None,
            "post_removed": r.post_removed is True,
            "post_removed_date": r.post_removed_date.isoformat() if r.post_removed_date else None,
        } for r in posts],
    }


@router.get("/events")
def recent_events(
    medium: str = Query(""),
    event_type: str = Query(""),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    _:  User    = Depends(require_case_manager),
):
    """Historial reciente de todas las cuentas de atacantes (para la vista general)."""
    medium = _check_medium(medium)
    if event_type and event_type not in EVENT_LABELS:
        raise HTTPException(status_code=422, detail="Tipo de evento inválido")
    query = (db.query(CaseAccountEvent, CaseAccount.author, CaseAccount.medium, Case.name, User.full_name)
             .join(CaseAccount, CaseAccount.id == CaseAccountEvent.account_id)
             .join(Case, Case.id == CaseAccountEvent.case_id)
             .outerjoin(User, User.id == CaseAccountEvent.created_by))
    if medium:
        query = query.filter(CaseAccount.medium == medium)
    if event_type:
        query = query.filter(CaseAccountEvent.event_type == event_type)
    total = query.count()
    rows = (query.order_by(func.coalesce(CaseAccountEvent.event_date, CaseAccountEvent.created_at).desc())
            .offset((page - 1) * 50).limit(50).all())
    return {
        "items": [{**_event_dict(e, by), "account_id": str(e.account_id), "author": author,
                   "medium": m, "case": case_name} for e, author, m, case_name, by in rows],
        "total": total, "page": page, "pages": max(1, -(-total // 50)),
        "types": EVENT_LABELS,
    }
