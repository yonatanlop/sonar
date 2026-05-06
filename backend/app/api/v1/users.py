import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.audit_utils import log_action
from app.api.deps import get_current_user, require_admin, require_analyst
from app.core.security import hash_password
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/users", tags=["Usuarios"])


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    password: str
    role: str = "viewer"


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    active: bool | None = None
    telegram_chat_id: str | None = None
    whatsapp_phone: str | None = None
    whatsapp_api_key: str | None = None
    notify_telegram: bool | None = None
    notify_whatsapp: bool | None = None
    notify_email: bool | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


def _user_to_dict(user: User) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "active": user.active,
        "telegram_chat_id": user.telegram_chat_id,
        "notify_telegram":  user.notify_telegram,
        "whatsapp_phone":   user.whatsapp_phone,
        "whatsapp_api_key": user.whatsapp_api_key,
        "notify_whatsapp":  user.notify_whatsapp,
        "notify_email":     user.notify_email,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "created_at": user.created_at.isoformat(),
    }


@router.get("/me")
def get_my_profile(current_user: User = Depends(get_current_user)):
    return _user_to_dict(current_user)


@router.put("/me")
def update_my_profile(data: UserUpdate,
                       current_user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    for field, value in data.model_dump(exclude_none=True).items():
        # Solo admin puede cambiar role y active
        if field in ("role", "active") and current_user.role != "admin":
            continue
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return _user_to_dict(current_user)


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(request: Request,
                    data: PasswordChange,
                    current_user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    from app.core.security import verify_password
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Contraseña actual incorrecta")
    current_user.password_hash = hash_password(data.new_password)
    log_action(db, current_user.id, "password_changed", request, "users", current_user.id)
    db.commit()


# ── Endpoint para analistas: lista simplificada de usuarios activos ──

@router.get("/active", dependencies=[Depends(require_analyst)])
def list_active_users(db: Session = Depends(get_db)):
    """Lista usuarios activos (admin + analyst) — accesible por analistas para configurar destinatarios."""
    users = (
        db.query(User)
        .filter(User.active == True, User.role.in_(["admin", "analyst"]))
        .order_by(User.full_name)
        .all()
    )
    return [{"id": str(u.id), "username": u.username, "full_name": u.full_name, "role": u.role} for u in users]


# ── Admin endpoints ──────────────────────────────────────────

@router.get("/", dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at).all()
    return [_user_to_dict(u) for u in users]


@router.post("/", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
def create_user(request: Request,
                data: UserCreate,
                current_user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    if db.query(User).filter(
        (User.username == data.username) | (User.email == data.email)
    ).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="El usuario o email ya existe")

    if data.role not in ("admin", "analyst", "viewer"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Rol inválido")

    user = User(
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        role=data.role,
        created_by=current_user.id,
    )
    db.add(user)
    db.flush()
    log_action(db, current_user.id, "user_created", request, "users", user.id,
               {"username": user.username, "role": user.role})
    db.commit()
    db.refresh(user)
    return _user_to_dict(user)


@router.put("/{user_id}", dependencies=[Depends(require_admin)])
def update_user(request: Request, user_id: uuid.UUID, data: UserUpdate,
                current_user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Usuario no encontrado")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    log_action(db, current_user.id, "user_updated", request, "users", user.id,
               {"username": user.username})
    db.commit()
    db.refresh(user)
    return _user_to_dict(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_admin)])
def deactivate_user(request: Request, user_id: uuid.UUID,
                    current_user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Usuario no encontrado")
    user.active = False
    log_action(db, current_user.id, "user_deactivated", request, "users", user.id,
               {"username": user.username})
    db.commit()
