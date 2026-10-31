"""Revoked-token list in Redis. Entries expire when the token itself would have."""

from datetime import UTC, datetime

from redis import Redis

from app.core.security import TokenClaims

_PREFIX = "auth:revoked:"


def revoke(redis: Redis, claims: TokenClaims) -> None:
    ttl = int((claims.expires_at - datetime.now(UTC)).total_seconds())
    if ttl > 0:
        redis.set(_PREFIX + claims.jti, "1", ex=ttl)


def is_revoked(redis: Redis, jti: str) -> bool:
    return bool(redis.exists(_PREFIX + jti))
