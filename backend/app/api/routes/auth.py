from fastapi import APIRouter, HTTPException, status

from app.api.deps import BearerCredentials, CurrentUser, DbSession, RedisClient, unauthorized
from app.core import token_store
from app.core.config import settings
from app.core.security import (
    TokenError,
    create_token,
    decode_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.models import User
from app.schemas.auth import LoginRequest, LoginResponse, LogoutRequest, RefreshRequest, TokenPair
from app.schemas.user import UserRead
from app.services.users import get_user_by_email

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user: User) -> TokenPair:
    access, _ = create_token(user.id, "access")
    refresh, _ = create_token(user.id, "refresh")
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_access_ttl_minutes * 60,
        refresh_expires_in=settings.jwt_refresh_ttl_days * 86400,
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: DbSession) -> LoginResponse:
    user = get_user_by_email(db, body.email)
    if not verify_password(body.password, user.hashed_password if user else None):
        raise unauthorized("Correo o contraseña incorrectos.")
    assert user is not None
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Usuario inactivo.")

    if password_needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(body.password)
        db.commit()

    tokens = _issue_tokens(user)
    return LoginResponse(**tokens.model_dump(), user=UserRead.model_validate(user))


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: DbSession, redis: RedisClient) -> TokenPair:
    """Exchange a refresh token for a new pair. The old refresh token stops working (rotation)."""
    try:
        claims = decode_token(body.refresh_token, "refresh")
    except TokenError:
        raise unauthorized("Refresh token inválido o expirado.") from None
    if token_store.is_revoked(redis, claims.jti):
        raise unauthorized("Refresh token ya utilizado o revocado.")

    user = db.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise unauthorized("Usuario inactivo o inexistente.")

    token_store.revoke(redis, claims)
    return _issue_tokens(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: LogoutRequest, redis: RedisClient, creds: BearerCredentials) -> None:
    """Revoke the refresh token (body) and the access token (header), if given and valid."""
    candidates = [
        (body.refresh_token, "refresh"),
        (creds.credentials if creds else None, "access"),
    ]
    for token, token_type in candidates:
        if not token:
            continue
        try:
            token_store.revoke(redis, decode_token(token, token_type))  # type: ignore[arg-type]
        except TokenError:
            pass  # already invalid; nothing to revoke


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> User:
    return user
