from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.shared.deps import get_db, require_admin, require_analyst
from app.modules.identity.application.schemas import UserCreate, UserUpdate, UserOut, UserMinimal
from app.modules.identity.application.user_service import UserService
from app.modules.identity.infrastructure.user_repository import SqlUserRepository

router = APIRouter(prefix="/users", tags=["Usuarios"])


def _svc(db: Session = Depends(get_db)) -> UserService:
    return UserService(SqlUserRepository(db))


@router.get("", response_model=list[UserOut])
def list_users(svc: UserService = Depends(_svc), _=Depends(require_admin)):
    return [UserOut(
        id=u.id, username=u.username, email=u.email,
        full_name=u.full_name, role=u.role, active=u.active,
        telegram_chat_id=u.telegram_chat_id,
    ) for u in svc.list_all()]


@router.get("/active", response_model=list[UserMinimal])
def list_active_users(svc: UserService = Depends(_svc), _=Depends(require_analyst)):
    return [UserMinimal(id=u.id, username=u.username, full_name=u.full_name, role=u.role)
            for u in svc.list_active()]


@router.post("", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, svc: UserService = Depends(_svc), _=Depends(require_admin)):
    u = svc.create(data)
    return UserOut(id=u.id, username=u.username, email=u.email,
                   full_name=u.full_name, role=u.role, active=u.active,
                   telegram_chat_id=u.telegram_chat_id)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: UUID, data: UserUpdate,
                svc: UserService = Depends(_svc), _=Depends(require_admin)):
    u = svc.update(user_id, data)
    return UserOut(id=u.id, username=u.username, email=u.email,
                   full_name=u.full_name, role=u.role, active=u.active,
                   telegram_chat_id=u.telegram_chat_id)


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: UUID, svc: UserService = Depends(_svc), _=Depends(require_admin)):
    svc.delete(user_id)
