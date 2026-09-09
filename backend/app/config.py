"""
MedFusion AI — Application Configuration.

All settings are loaded from environment variables.
Never hardcode secrets or credentials.
"""

from functools import lru_cache
from typing import List

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
    database_url: str | None = None

    @property
    def effective_database_url(self) -> str:
        """Build database URL from components if not explicitly set."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """Synchronous database URL for Alembic migrations."""
        return self.effective_database_url.replace(
            "postgresql+asyncpg", "postgresql+psycopg2"
        )

    # --- JWT / Auth ---
    secret_key: str = "CHANGE_ME_generate_a_random_64_char_string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # --- Security ---
    bcrypt_rounds: int = 12
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    rate_limit_per_minute: int = 100
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origin_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # --- File Storage ---
    upload_dir: str = "./uploads"
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
