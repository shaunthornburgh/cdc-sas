"""Password hashing (argon2id) and JWT creation/validation."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings

TokenType = Literal["access", "refresh"]

_hasher = PasswordHasher()
# Used when the email doesn't exist so a failed login takes the same time either way.
_DUMMY_HASH = _hasher.hash("timing-equaliser")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    try:
        return _hasher.verify(hashed or _DUMMY_HASH, password) and hashed is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(hashed: str) -> bool:
    return _hasher.check_needs_rehash(hashed)


class TokenError(Exception):
    pass


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    jti: str
    type: TokenType
    expires_at: datetime


def create_token(user_id: uuid.UUID, token_type: TokenType) -> tuple[str, TokenClaims]:
    now = datetime.now(UTC)
    ttl = (
        timedelta(minutes=settings.jwt_access_ttl_minutes)
        if token_type == "access"
        else timedelta(days=settings.jwt_refresh_ttl_days)
    )
    claims = TokenClaims(
        user_id=user_id, jti=uuid.uuid4().hex, type=token_type, expires_at=now + ttl
    )
    payload = {
        "sub": str(user_id),
        "jti": claims.jti,
        "type": token_type,
        "iat": now,
        "exp": claims.expires_at,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, claims


def decode_token(token: str, expected_type: TokenType) -> TokenClaims:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "jti", "type", "exp"]},
        )
        if payload["type"] != expected_type:
            raise TokenError("wrong token type")
        return TokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            jti=payload["jti"],
            type=payload["type"],
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise TokenError(str(exc)) from exc
