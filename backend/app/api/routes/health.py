from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.deps import DbSession, RedisClient
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness: the process is up."""
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@router.get("/health/ready")
def ready(response: Response, db: DbSession, redis: RedisClient) -> dict:
    """Readiness: Postgres and Redis are reachable."""
    checks: dict[str, str] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc.__class__.__name__}"

    try:
        redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc.__class__.__name__}"

    healthy = all(v == "ok" for v in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "degraded", "checks": checks}
