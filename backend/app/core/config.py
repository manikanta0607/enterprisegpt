"""Centralized configuration management for the EnterpriseGPT backend.

All runtime configuration is sourced from environment variables (or a `.env`
file during local development). This module is the single source of truth
for configuration and must never be bypassed by reading `os.environ`
directly elsewhere in the codebase.
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables.

    Attributes:
        environment: Deployment environment name (local, staging, production).
        debug: Whether debug mode (verbose errors, auto-reload) is enabled.
        project_name: Human-readable project name, used in API docs.
        api_v1_prefix: URL prefix for version 1 of the API.
        allowed_origins: List of origins permitted by CORS middleware.
        postgres_host: Hostname of the PostgreSQL server.
        postgres_port: Port of the PostgreSQL server.
        postgres_user: PostgreSQL username.
        postgres_password: PostgreSQL password.
        postgres_db: PostgreSQL database name.
        redis_host: Hostname of the Redis server.
        redis_port: Port of the Redis server.
        redis_db: Redis logical database index.
        minio_endpoint: MinIO server endpoint (host:port).
        minio_access_key: MinIO access key.
        minio_secret_key: MinIO secret key.
        minio_bucket_name: Default bucket used for document storage.
        minio_secure: Whether to use HTTPS when talking to MinIO.
        log_level: Minimum log level emitted by the application logger.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- General ---
    environment: str = Field(default="local", description="Deployment environment")
    debug: bool = Field(default=True, description="Enable debug mode")
    project_name: str = Field(default="EnterpriseGPT", description="Project display name")
    api_v1_prefix: str = Field(default="/api/v1", description="API v1 URL prefix")
    allowed_origins_raw: str = Field(
        default="http://localhost:3000",
        alias="ALLOWED_ORIGINS",
        description="Comma-separated CORS allowed origins",
    )

    # --- PostgreSQL ---
    postgres_host: str = Field(default="localhost", description="Postgres host")
    postgres_port: int = Field(default=5432, description="Postgres port")
    postgres_user: str = Field(default="enterprisegpt", description="Postgres user")
    postgres_password: str = Field(default="enterprisegpt", description="Postgres password")
    postgres_db: str = Field(default="enterprisegpt", description="Postgres database name")

    # --- Redis ---
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis logical DB index")

    # --- MinIO ---
    minio_endpoint: str = Field(default="localhost:9000", description="MinIO endpoint")
    minio_access_key: str = Field(default="minioadmin", description="MinIO access key")
    minio_secret_key: str = Field(default="minioadmin", description="MinIO secret key")
    minio_bucket_name: str = Field(default="enterprisegpt-documents", description="Default bucket")
    minio_secure: bool = Field(default=False, description="Use HTTPS for MinIO")

    # --- Logging ---
    log_level: str = Field(default="INFO", description="Application log level")

    # --- Auth: JWT ---
    jwt_secret_key: str = Field(
        default="CHANGE_ME_IN_PRODUCTION", description="Secret key used to sign JWTs"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    access_token_expire_minutes: int = Field(
        default=30, description="Access token lifetime in minutes"
    )
    refresh_token_expire_days: int = Field(
        default=14, description="Refresh token lifetime in days"
    )

    # --- Auth: Google OAuth ---
    google_client_id: str = Field(default="", description="Google OAuth client ID")

    # --- Google AI: Embeddings & Generation ---
    google_api_key: str = Field(
        default="", description="Google AI Studio API key for embeddings/generation"
    )
    embedding_model: str = Field(
        default="models/text-embedding-004", description="Google embedding model name"
    )
    embedding_dimensions: int = Field(
        default=768, description="Output dimensionality of the embedding model"
    )
    query_rewrite_model: str = Field(
        default="models/gemini-1.5-flash", description="Lightweight model used for query rewriting"
    )

    @property
    def allowed_origins(self) -> List[str]:
        """Parse the comma-separated origins string into a list.

        Returns:
            A list of CORS origin strings.
        """
        return [origin.strip() for origin in self.allowed_origins_raw.split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        """Build the async SQLAlchemy database URL.

        Returns:
            A `postgresql+asyncpg://` connection string.
        """
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Build the Redis connection URL.

        Returns:
            A `redis://` connection string.
        """
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of application settings.

    Using `lru_cache` ensures environment variables are parsed once and
    reused across the application, which is important for performance
    since `Settings` is injected as a FastAPI dependency on every request.

    Returns:
        The cached `Settings` instance.
    """
    return Settings()
