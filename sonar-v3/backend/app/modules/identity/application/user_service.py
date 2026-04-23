from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime, timezone

from app.modules.identity.domain.user import User
from app.modules.identity.domain.ports import IUserRepository
from app.modules.identity.application.schemas import UserCreate, UserUpdate
from app.shared.security import hash_password, verify_password, create_access_token
from app.shared.exceptions import NotFoundError, ConflictError, UnauthorizedError
from app.shared.types import UserRole


class UserService:
    def __init__(self, repo: IUserRepository):
        self._repo = repo

    def list_all(self) -> list[User]:
        return self._repo.list_all()

    def list_active(self) -> list[User]:
        return self._repo.list_active()

    def get(self, user_id: UUID) -> User:
        user = self._repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("Usuario no encontrado")
        return user

    def create(self, data: UserCreate) -> User:
        existing = self._repo.get_by_username(data.username)
        if existing:
            raise ConflictError("El nombre de usuario ya existe")
        now = datetime.now(timezone.utc)
        user = User(
            id=uuid4(),
            username=data.username,
            email=data.email,
            full_name=data.full_name,
            role=data.role,
            active=True,
            hashed_password=hash_password(data.password),
            telegram_chat_id=data.telegram_chat_id,
            created_at=now,
            updated_at=now,
        )
        return self._repo.create(user)

    def update(self, user_id: UUID, data: UserUpdate) -> User:
        user = self.get(user_id)
        if data.email is not None:
            user.email = data.email
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.role is not None:
            user.role = data.role
        if data.active is not None:
            user.active = data.active
        if data.telegram_chat_id is not None:
            user.telegram_chat_id = data.telegram_chat_id
        if data.password is not None:
            user.hashed_password = hash_password(data.password)
        user.updated_at = datetime.now(timezone.utc)
        return self._repo.update(user)

    def delete(self, user_id: UUID) -> None:
        self.get(user_id)
        self._repo.delete(user_id)

    def authenticate(self, username: str, password: str) -> str:
        user = self._repo.get_by_username(username)
        if not user or not user.active:
            raise UnauthorizedError("Credenciales inválidas")
        if not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Credenciales inválidas")
        return create_access_token({"sub": str(user.id)})

    def change_password(self, user_id: UUID, current: str, new: str) -> None:
        user = self.get(user_id)
        if not verify_password(current, user.hashed_password):
            raise UnauthorizedError("Contraseña actual incorrecta")
        user.hashed_password = hash_password(new)
        user.updated_at = datetime.now(timezone.utc)
        self._repo.update(user)
