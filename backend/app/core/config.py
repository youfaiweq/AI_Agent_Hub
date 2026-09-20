"""Environment-backed application settings."""

from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    app_name: str = "AgentHub"
    app_version: str = "1.0.0"
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
    qdrant_url: str = "http://127.0.0.1:6333"
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
    reranker_provider: str = "cohere"
    reranker_base_url: str = "https://api.cohere.com/v2"
    reranker_api_key: SecretStr = SecretStr("")
    reranker_model_name: str = "rerank-v3.5"
    reranker_timeout_seconds: float = 10.0
    reranker_fallback_enabled: bool = False
    reranker_top_k: int = 5
    agent_max_steps: int = 10
    agent_timeout_seconds: float = 30.0
    agent_approval_timeout_seconds: float = Field(default=900.0, gt=0)
    agent_router_model: str = "qwen-flash"
    agent_history_max_messages: int = 8
    agent_context_token_budget: int = 2000
    agent_tool_results_max: int = 4
    tool_timeout_seconds: float = 30.0
    langfuse_enabled: bool = False
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_public_key: SecretStr = SecretStr("")
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_timeout_seconds: float = Field(default=3.0, gt=0)
    chat_history_max_messages: int = 8
    chat_context_token_budget: int = 2000
    chat_retrieval_top_k: int = 5
    sql_allowed_tables: list[str] = Field(default_factory=list)
    sql_timeout_seconds: float = 5.0
    sql_row_limit: int = 100
    web_search_provider: str = "tavily"
    web_search_base_url: str = "https://api.tavily.com"
    web_search_api_key: SecretStr = SecretStr("")
    web_search_timeout_seconds: float = 10.0
    web_search_max_results: int = 5
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
