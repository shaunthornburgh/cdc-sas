from redis import Redis

from app.core.config import settings

redis_client: Redis = Redis.from_url(
    settings.redis_url, decode_responses=True, socket_connect_timeout=2
)


def get_redis() -> Redis:
    """FastAPI dependency (overridden in tests with fakeredis)."""
    return redis_client
