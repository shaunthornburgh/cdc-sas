from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "dev-only-insecure-jwt-secret-change-me-please"


class Settings(BaseSettings):
    """App settings, read from environment variables and backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Casa Dolce Casa API"
    environment: str = "local"  # local | test | staging | production
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://cdc:cdc@localhost:5432/cdc"
    redis_url: str = "redis://localhost:6379/0"

    # Comma-separated, e.g. "http://localhost:3000,https://app.example.com"
    cors_origins: str = "http://localhost:3000"

    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 7

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.environment in {"local", "test"}

    @model_validator(mode="after")
    def _require_real_secret_outside_dev(self) -> "Settings":
        if not self.is_dev and (self.jwt_secret == DEFAULT_JWT_SECRET or len(self.jwt_secret) < 32):
            raise ValueError(
                "JWT_SECRET must be set to a random value of 32+ chars outside local/test"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
