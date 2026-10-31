from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis import Redis
from sqlalchemy.orm import Session

from app.core import token_store
from app.core.redis import get_redis
from app.core.security import TokenError, decode_token
from app.db.session import get_db
from app.models import User

DbSession = Annotated[Session, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]

bearer_scheme = HTTPBearer(auto_error=False, description="Access token from /auth/login")
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def unauthorized(detail: str = "No autenticado.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(db: DbSession, redis: RedisClient, creds: BearerCredentials) -> User:
    if creds is None:
        raise unauthorized()
    try:
        claims = decode_token(creds.credentials, "access")
    except TokenError:
        raise unauthorized("Token inválido o expirado.") from None
    if token_store.is_revoked(redis, claims.jti):
        raise unauthorized("Sesión cerrada.")

    user = db.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise unauthorized("Usuario inactivo o inexistente.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
