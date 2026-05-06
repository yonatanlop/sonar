from app.models.user import AuditLog


def log_action(db, user_id, action, request=None, target_table=None, target_id=None, details=None):
    db.add(AuditLog(
        user_id=user_id,
        action=action,
        target_table=target_table,
        target_id=target_id,
        details=details,
        ip_address=request.client.host if request and request.client else None,
    ))
