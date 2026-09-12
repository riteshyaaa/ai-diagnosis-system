"""
MedFusion AI — Application Configuration.

All settings are loaded from environment variables.
Never hardcode secrets or credentials.
"""

from functools import lru_cache
from typing import List, Optional
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "MedFusion AI"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # --- Server ---
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_workers: int = 1

    # --- Database ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "medfusion_db"
    postgres_user: str = "medfusion_user"
    postgres_password: str = "changeme"
    database_url: Optional[str] = None
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    @property
    def effective_database_url(self) -> str:
        """Build database URL from components if not explicitly set."""
        if self.database_url:
            return self.database_url
        user = quote_plus(self.postgres_user)
        pwd = quote_plus(self.postgres_password)
        return (
            f"postgresql+asyncpg://{user}:{pwd}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """Synchronous database URL for Alembic migrations."""
        return self.effective_database_url.replace(
            "postgresql+asyncpg", "postgresql+psycopg2"
        )

    # --- JWT / Auth ---
    jwt_secret_key: str = Field(
        default="CHANGE_ME_generate_a_random_64_char_string_for_production_use",
        validation_alias="secret_key",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        validation_alias="access_token_expire_minutes",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        validation_alias="refresh_token_expire_days",
    )

    # --- Security ---
    bcrypt_rounds: int = 12
    max_login_attempts: int = 5
    account_lockout_minutes: int = Field(
        default=15,
        validation_alias="lockout_duration_minutes",
    )
    rate_limit_per_minute: int = 100
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origin_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # --- File Storage ---
    upload_dir: str = "./uploads"
    storage_dir: str = "./storage"
    max_upload_size_mb: int = 50
    allowed_image_types: str = "image/jpeg,image/png,application/dicom"

    @property
    def allowed_image_type_list(self) -> List[str]:
        return [t.strip() for t in self.allowed_image_types.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    # --- ML Models ---
    model_dir: str = "./models/registry"
    default_image_model: str = "densenet121_v1"
    default_tabular_model: str = "xgboost_heart_v1"
    default_fusion_model: str = "late_fusion_v1"
    inference_device: str = "cpu"

    # --- MLflow ---
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "medfusion-ai"

    # --- Logging ---
    log_level: str = "INFO"
    log_format: str = "json"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance (singleton per process)."""
    return Settings()
