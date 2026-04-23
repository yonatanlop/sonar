from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.shared.database import SessionLocal
from app.shared.exceptions import UnauthorizedError, ForbiddenError
from app.shared.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v3/auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            raise UnauthorizedError()
    except JWTError:
        raise UnauthorizedError("Token inválido o expirado")

    # Import here to avoid circular imports at module load time
    from app.modules.identity.infrastructure.orm import UserORM
    user = db.query(UserORM).filter(UserORM.id == user_id, UserORM.active == True).first()
    if not user:
        raise UnauthorizedError("Usuario no encontrado o inactivo")
    return user


def require_admin(current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise ForbiddenError("Se requiere rol de administrador")
    return current_user


def require_analyst(current_user=Depends(get_current_user)):
    if current_user.role not in ("admin", "analyst"):
        raise ForbiddenError("Se requiere rol de analista o superior")
    return current_user
