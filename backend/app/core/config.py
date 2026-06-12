from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_async_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = ""
    frontend_origin: str = "http://localhost:3000"
    client_token_secret: str = "dev-secret-change-in-production"
    room_code_secret: str = "dev-room-secret"
    simulation_version: str = "1.0.0"
    pick_timer_seconds: int = 30

    @field_validator("database_url", mode="after")
    @classmethod
    def require_postgres_url(cls, value: str, info) -> str:
        environment = info.data.get("environment", "development")
        if not value:
            if environment == "test":
                return "sqlite+aiosqlite:///:memory:"
            raise ValueError(
                "DATABASE_URL is required. Use your Supabase Postgres URI "
                "(postgresql+asyncpg://... or postgresql://...)."
            )
        if "sqlite" in value:
            if environment == "test":
                return value
            raise ValueError("SQLite is not supported. Set DATABASE_URL to your Supabase Postgres URI.")
        return normalize_async_database_url(value)


settings = Settings()
