"""Environment-backed application settings."""

from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    app_name: str = "AgentHub"
    app_version: str = "0.2.0"
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT", "APP_ENV"),
    )
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    database_url: str = "postgresql+asyncpg://agenthub:agenthub@localhost:55432/agenthub"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection_prefix: str = "agenthub_kb"
    embedding_provider: str = "hash"
    embedding_model_name: str = "hash-v1"
    embedding_dimension: int = 384
    retrieval_score_threshold: float = 0.2
    llm_provider: str = "openai_compatible"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 30.0
    llm_temperature: float = 0.2
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "agenthub"
    minio_secret_key: str = "agenthub-secret"
    minio_secure: bool = False
    minio_bucket: str = "agenthub"
    health_timeout_seconds: float = 3.0
    integration_timeout_seconds: float = 3.0
    jwt_secret_key: SecretStr = SecretStr("development-only-change-this-secret")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    max_document_size_bytes: int = 10 * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings."""

    return Settings()
