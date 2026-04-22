from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.shared.deps import get_db, get_current_user
from app.modules.identity.application.schemas import TokenOut, UserOut, PasswordChange
from app.modules.identity.application.user_service import UserService
from app.modules.identity.infrastructure.user_repository import SqlUserRepository

router = APIRouter(prefix="/auth", tags=["Auth"])


def _svc(db: Session = Depends(get_db)) -> UserService:
    return UserService(SqlUserRepository(db))


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), svc: UserService = Depends(_svc)):
    token = svc.authenticate(form.username, form.password)
    user = svc._repo.get_by_username(form.username)
    return TokenOut(access_token=token, user=UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        active=user.active,
        telegram_chat_id=user.telegram_chat_id,
    ))


@router.get("/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        active=current_user.active,
        telegram_chat_id=current_user.telegram_chat_id,
    )


@router.post("/change-password", status_code=204)
def change_password(
    data: PasswordChange,
    current_user=Depends(get_current_user),
    svc: UserService = Depends(_svc),
):
    svc.change_password(current_user.id, data.current_password, data.new_password)
