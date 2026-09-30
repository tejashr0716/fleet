from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://fleet:fleet@localhost:5432/fleet"
    redis_url: str = "redis://localhost:6379/0"
    admin_username: str = "admin"
    admin_password: SecretStr = SecretStr("change-this-demo-password")
    jwt_secret: SecretStr = SecretStr("local-demo-only-change-this-32-character-secret")
    device_api_key: SecretStr = SecretStr("local-demo-device-key-change-this")
    allowed_origins: str = (
        "http://localhost:8000,http://127.0.0.1:8000,https://tejashr0716.github.io"
    )
    token_ttl_minutes: int = 30
    live_ttl_seconds: int = 30
    speed_limit_kmh: float = 80
    outbox_poll_seconds: float = 0.2

    @property
    def origins(self) -> list[str]:
        return [x.strip() for x in self.allowed_origins.split(",") if x.strip()]

    @model_validator(mode="after")
    def production_safety(self):
        if not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("Use PostgreSQL with the asyncpg driver")
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("Unknown environment")
        if (
            self.token_ttl_minutes <= 0
            or self.live_ttl_seconds <= 0
            or self.outbox_poll_seconds <= 0
        ):
            raise ValueError("TTL and polling intervals must be positive")
        if self.environment == "production":
            values = [self.jwt_secret.get_secret_value(), self.device_api_key.get_secret_value()]
            if any(len(v) < 32 or "demo" in v.lower() or "change" in v.lower() for v in values):
                raise ValueError(
                    "Production requires independently generated JWT and device secrets"
                )
            password = self.admin_password.get_secret_value()
            if len(password) < 12 or password == "change-this-demo-password":
                raise ValueError(
                    "Production requires a new admin password of at least 12 characters"
                )
            if "*" in self.origins or not self.origins:
                raise ValueError("Production requires explicit allowed origins")
        return self
