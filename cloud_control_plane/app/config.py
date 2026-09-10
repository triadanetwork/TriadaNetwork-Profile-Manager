from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRIADA_CLOUD_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8100
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://triada:triada@localhost:5432/triada"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-only-change-me"
    jwt_ttl_minutes: int = 30
    refresh_ttl_days: int = 30
    cors_origins: list[str] = ["http://localhost:3000"]
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle_seconds: int = 1800
    rate_limit_per_minute: int = 120
    log_level: str = "INFO"
    trusted_proxy_count: int = 1
    metrics_enabled: bool = True
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.0
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "triada-cloud"
    worker_concurrency: int = 2

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}

    @model_validator(mode="after")
    def validate_secret(self):
        if self.is_production:
            if self.host not in {"0.0.0.0", "::"}:
                raise ValueError("TRIADA_CLOUD_HOST must listen on a container interface in production")
            if self.jwt_secret == "dev-only-change-me" or len(self.jwt_secret) < 48:
                raise ValueError("TRIADA_CLOUD_JWT_SECRET must be a production secret of at least 48 characters")
            if any(origin.startswith("http://localhost") for origin in self.cors_origins):
                raise ValueError("TRIADA_CLOUD_CORS_ORIGINS must not use localhost in production")
            if self.rate_limit_per_minute <= 0:
                raise ValueError("TRIADA_CLOUD_RATE_LIMIT_PER_MINUTE must be > 0 in production")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
