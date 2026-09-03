"""Application configuration loaded from environment variables.

All runtime configuration lives here. Nothing in the app should read
os.environ directly outside of this module.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_env: str = "development"
    app_name: str = "LLM Gateway"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Security
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Database
    database_url: str

    # Redis
    redis_url: str
    cache_ttl_seconds: int = 3600
    cache_temperature_threshold: float = 0.0

    # LLM Providers
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    ollama_base_url: str = "http://localhost:11434"

    # Rate limiting
    rate_limit_per_minute: int = 60

    # Request size limits
    max_request_body_bytes: int = 10 * 1024 * 1024  # 10 MiB

    # Routing
    routing_rules_path: str = "app/core/routing_rules.yaml"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — use as a FastAPI dependency."""
    return Settings()  # type: ignore[call-arg]
