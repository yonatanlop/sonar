import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import redis as redis_lib
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.SESSION_TIMEOUT_MINUTES)
    )
    return jwt.encode(
        {"sub": subject, "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def get_token_exp(token: str) -> Optional[int]:
    """Retorna el timestamp de expiración del token sin verificar firma."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload.get("exp")
    except JWTError:
        return None


# ── Blacklist de tokens (Redis) ────────────────────────────────

_redis_pool = redis_lib.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)


def _redis() -> redis_lib.Redis:
    return redis_lib.Redis(connection_pool=_redis_pool)


def _blacklist_key(token: str) -> str:
    digest = hashlib.sha256(token.encode()).hexdigest()
    return f"token_blacklist:{digest}"


def blacklist_token(token: str) -> None:
    """Invalida un token almacenándolo en Redis hasta que expire naturalmente."""
    exp = get_token_exp(token)
    if exp is None:
        return
    ttl = int(exp - datetime.now(timezone.utc).timestamp())
    if ttl <= 0:
        return  # Ya expiró, no hace falta guardarlo
    try:
        _redis().setex(_blacklist_key(token), ttl, "1")
    except Exception:
        pass  # Si Redis no está disponible, no bloqueamos el logout


def is_token_blacklisted(token: str) -> bool:
    """Devuelve True si el token fue invalidado por logout."""
    try:
        return _redis().exists(_blacklist_key(token)) > 0
    except Exception:
        return False  # Ante duda, permitir (evita bloquear usuarios si Redis falla)
