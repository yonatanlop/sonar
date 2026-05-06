import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_admin
from app.database import get_db
from app.models.user import AuditLog, User

router = APIRouter(prefix="/audit", tags=["Auditoría"])

PAGE_SIZE = 50

ACTION_LABELS = {
    "login":              "Inicio de sesión",
    "logout":             "Cierre de sesión",
    "user_created":       "Usuario creado",
    "user_updated":       "Usuario editado",
    "user_deactivated":   "Usuario desactivado",
    "password_changed":   "Contraseña cambiada",
    "entity_created":     "Entidad creada",
    "entity_updated":     "Entidad editada",
    "alias_added":        "Alias agregado",
    "alias_deleted":      "Alias eliminado",
    "keyword_added":      "Keyword agregada",
    "keyword_deleted":    "Keyword eliminada",
    "alert_acknowledged": "Alerta reconocida",
    "rule_created":       "Regla creada",
    "rule_deleted":       "Regla eliminada",
    "rule_toggled":       "Regla activada/desactivada",
    "report_generated":   "Reporte generado",
    "report_downloaded":  "Reporte descargado",
    "yt_channel_added":   "Canal YouTube agregado",
    "yt_channel_deleted": "Canal YouTube eliminado",
    "yt_videos_saved":    "Videos YouTube guardados",
    "twitter_feed_added": "Feed Twitter agregado",
    "twitter_feed_deleted": "Feed Twitter eliminado",
}

MODULES = {
    "users":            "Usuarios",
    "entities":         "Entidades",
    "alerts":           "Alertas",
    "alert_rules":      "Reglas de alerta",
    "reports":          "Reportes",
    "youtube_channels": "YouTube Explorer",
    "twitter_feeds":    "Twitter Explorer",
}


@router.get("")
def list_audit_logs(
    page:         int                    = Query(1, ge=1),
    user_id:      Optional[uuid.UUID]   = Query(None),
    action:       Optional[str]          = Query(None),
    target_table: Optional[str]          = Query(None),
    from_date:    Optional[datetime]     = Query(None),
    to_date:      Optional[datetime]     = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    query = (
        db.query(AuditLog)
        .options(joinedload(AuditLog.user))
    )

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if target_table:
        query = query.filter(AuditLog.target_table == target_table)
    if from_date:
        query = query.filter(AuditLog.created_at >= from_date)
    if to_date:
        query = query.filter(AuditLog.created_at <= to_date)

    total = query.count()
    logs  = (
        query
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .all()
    )

    items = [
        {
            "id":           str(log.id),
            "username":     log.user.username  if log.user else "—",
            "full_name":    log.user.full_name if log.user else "—",
            "action":       log.action,
            "action_label": ACTION_LABELS.get(log.action, log.action),
            "target_table": log.target_table,
            "module_label": MODULES.get(log.target_table, log.target_table or "—"),
            "target_id":    str(log.target_id) if log.target_id else None,
            "details":      log.details,
            "ip_address":   log.ip_address,
            "created_at":   log.created_at.isoformat(),
        }
        for log in logs
    ]

    return {
        "items": items,
        "total": total,
        "page":  page,
        "pages": max(1, -(-total // PAGE_SIZE)),
    }


@router.get("/users")
def list_audit_users(db: Session = Depends(get_db), _=Depends(require_admin)):
    """Lista de usuarios que tienen registros en audit_log — para el filtro del frontend."""
    rows = (
        db.query(User.id, User.username, User.full_name)
        .join(AuditLog, AuditLog.user_id == User.id)
        .distinct()
        .order_by(User.full_name)
        .all()
    )
    return [{"id": str(r.id), "username": r.username, "full_name": r.full_name} for r in rows]
