"""
Application Configuration Module.

Loads configuration from environment variables and local .env file.
Gracefully handles both pydantic-settings (when installed) and native os.getenv fallback.
Automatically normalizes postgres:// and postgresql:// to postgresql+psycopg:// for SQLAlchemy 2.0.
"""
import os
from pathlib import Path


def _normalize_database_url(url: str) -> str:
    """Normalize Postgres URLs (e.g. from Railway/Heroku) to use psycopg driver."""
    if not url:
        return "postgresql+psycopg://postgres:postgres@localhost:5432/darktrace_pod2"
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _load_dotenv(dotenv_path: str = ".env") -> None:
    """Simple parser to load .env into os.environ if python-dotenv is not installed."""
    env_file = Path(dotenv_path)
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key not in os.environ:
                    os.environ[key] = val


_load_dotenv()

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import field_validator

    class Settings(BaseSettings):
        APP_NAME: str = "DarkTrace M1 Pod 2 Backend"
        ENVIRONMENT: str = "development"
        DEBUG: bool = True
        API_V1_PREFIX: str = "/api/v1"

        # Default PostgreSQL target
        DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/darktrace_pod2"

        DB_POOL_SIZE: int = 5
        DB_MAX_OVERFLOW: int = 10
        DB_POOL_TIMEOUT: int = 30

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore"
        )

        @field_validator("DATABASE_URL", mode="after")
        @classmethod
        def validate_database_url(cls, v: str) -> str:
            return _normalize_database_url(v)

    settings = Settings()

except ImportError:
    class SettingsFallback:
        def __init__(self):
            self.APP_NAME: str = os.getenv("APP_NAME", "DarkTrace M1 Pod 2 Backend")
            self.ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
            self.DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
            self.API_V1_PREFIX: str = os.getenv("API_V1_PREFIX", "/api/v1")
            raw_url = os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg://postgres:postgres@localhost:5432/darktrace_pod2"
            )
            self.DATABASE_URL: str = _normalize_database_url(raw_url)
            self.DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
            self.DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
            self.DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))

    settings = SettingsFallback()
