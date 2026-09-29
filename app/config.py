"""Application configuration loaded strictly via pydantic-settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for Fleet platform.

    All environment variables are loaded through this settings class.
    Direct calls to os.environ are disallowed across the codebase.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/fleet",
        description="Async PostgreSQL / TimescaleDB connection URI",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URI",
    )
    cors_origins: str = "https://tejashr0716.github.io,http://localhost:8000,http://127.0.0.1:8000"
    ws_allowed_origins: str = (
        "https://tejashr0716.github.io,http://localhost:8000,http://127.0.0.1:8000"
    )

    stream_name: str = "stream:positions"
    consumer_group: str = "cg:positions"
    consumer_name: str = "worker-1"
    batch_max_size: int = 500
    batch_max_wait_ms: int = 200
    h3_resolution: int = 8
    speed_limit_kmh: float = 80.0
    idle_timeout_seconds: int = 300
    signal_lost_ttl_seconds: int = 30
    max_ws_connections: int = 5000
    consumer_lag_unhealthy: int = 10000
    position_retention_days: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        """Parsed list of allowed HTTP CORS origins."""
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def ws_allowed_origin_list(self) -> list[str]:
        """Parsed list of allowed WebSocket origins."""
        return [item.strip() for item in self.ws_allowed_origins.split(",") if item.strip()]


settings = Settings()
