from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.identity.domain.user import User
from app.modules.identity.domain.ports import IUserRepository
from app.modules.identity.infrastructure.orm import UserORM


class SqlUserRepository(IUserRepository):
    def __init__(self, db: Session):
        self._db = db

    def get_by_id(self, user_id: UUID) -> User | None:
        row = self._db.query(UserORM).filter(UserORM.id == str(user_id)).first()
        return row.to_domain() if row else None

    def get_by_username(self, username: str) -> User | None:
        row = self._db.query(UserORM).filter(UserORM.username == username).first()
        return row.to_domain() if row else None

    def list_active(self) -> list[User]:
        rows = self._db.query(UserORM).filter(UserORM.active == True).all()
        return [r.to_domain() for r in rows]

    def list_all(self) -> list[User]:
        rows = self._db.query(UserORM).order_by(UserORM.username).all()
        return [r.to_domain() for r in rows]

    def create(self, user: User) -> User:
        row = UserORM.from_domain(user)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def update(self, user: User) -> User:
        row = self._db.query(UserORM).filter(UserORM.id == str(user.id)).first()
        if not row:
            return user
        row.email = user.email
        row.full_name = user.full_name
        row.role = user.role.value if hasattr(user.role, 'value') else user.role
        row.active = user.active
        row.hashed_password = user.hashed_password
        row.telegram_chat_id = user.telegram_chat_id
        row.updated_at = user.updated_at
        self._db.commit()
        self._db.refresh(row)
        return row.to_domain()

    def delete(self, user_id: UUID) -> None:
        self._db.query(UserORM).filter(UserORM.id == str(user_id)).delete()
        self._db.commit()
