from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, oauth2_scheme
from app.core.config import settings
from app.core.security import blacklist_token, create_access_token, verify_password
from app.database import get_db
from app.models.user import AuditLog, User

router = APIRouter(prefix="/auth", tags=["Autenticación"])


class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict


@router.post("/login", response_model=Token)
def login(request: Request,
          form_data: OAuth2PasswordRequestForm = Depends(),
          db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.username == form_data.username,
        User.active == True
    ).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    # Registrar último login
    user.last_login = datetime.now(timezone.utc)

    # Auditoría
    db.add(AuditLog(
        user_id=user.id,
        action="login",
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()

    token = create_access_token(subject=str(user.id))
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.SESSION_TIMEOUT_MINUTES * 60,
        "user": {
            "id": str(user.id),
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "is_superadmin": bool(getattr(user, "is_superadmin", False)),
        },
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Invalida el token actual añadiéndolo a la blacklist de Redis.
    El token queda inútil aunque no haya expirado.
    """
    blacklist_token(token)
    db.add(AuditLog(
        user_id=current_user.id,
        action="logout",
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()
