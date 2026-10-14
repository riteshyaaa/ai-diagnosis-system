"""
MedFusion AI — Application Configuration.

All settings are loaded from environment variables.
Never hardcode secrets or credentials.
"""

from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import quote_plus, unquote, urlsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **values: Any) -> None:
        super().__init__(**values)
        self._normalize_local_paths()
        self._validate_production_configuration()

    def _normalize_local_paths(self) -> None:
        """Resolve docker container paths like /app/uploads to local workspace when outside docker."""
        import os
        if os.name == "nt" or not (Path("/app").exists() and not Path("/app").drive):
            for field_name in ("upload_dir", "storage_dir", "model_dir"):
                val = getattr(self, field_name, None)
                if val and str(val).replace("\\", "/").startswith("/app/"):
                    sub = str(val).replace("\\", "/").split("/app/", 1)[-1]
                    setattr(self, field_name, str((PROJECT_ROOT / sub).resolve()))

    def _validate_production_configuration(self) -> None:
        """Reject development defaults when the app is explicitly in production."""
        if self.app_env.strip().lower() not in {"prod", "production"}:
            return

        problems = []
        if self.debug:
            problems.append("DEBUG must be false")
        if self.demo_users_enabled:
            problems.append("DEMO_USERS_ENABLED must be false")

        secret = self.jwt_secret_key.strip()
        if len(secret) < 32 or "change_me" in secret.lower():
            problems.append("SECRET_KEY must be a non-placeholder value of at least 32 characters")

        database = urlsplit(self.effective_database_url)
        database_host = (database.hostname or "").lower().rstrip(".")
        try:
            database_is_loopback = bool(database_host) and ip_address(database_host).is_loopback
        except ValueError:
            database_is_loopback = database_host == "localhost"
        database_username = unquote(database.username or "")
        database_password = unquote(database.password or "")
        if database.scheme != "postgresql+asyncpg":
            problems.append("DATABASE_URL must use PostgreSQL with asyncpg")
        if not database_host or database_is_loopback:
            problems.append("DATABASE_URL must name a non-local database host")
        if (
            len(database_username) < 8
            or database_username.lower() in {"medfusion_user", "postgres", "username", "user"}
            or len(database_password) < 16
            or "change_me" in database_password.lower()
            or database_password.lower() in {"changeme", "password", "password123", "your_password"}
        ):
            problems.append("DATABASE_URL must contain configured database credentials")

        origins = self.cors_origin_list
        invalid_origins = False
        for origin in origins:
            parsed_origin = urlsplit(origin)
            if (
                origin == "*"
                or parsed_origin.scheme != "https"
                or not parsed_origin.hostname
                or parsed_origin.path
                or parsed_origin.query
                or parsed_origin.fragment
                or parsed_origin.username
                or parsed_origin.password
            ):
                invalid_origins = True
                break
        if not origins or invalid_origins:
            problems.append("CORS_ORIGINS must contain explicit HTTPS origins")

        if problems:
            raise ValueError("Unsafe production configuration: " + "; ".join(problems))

    # --- Application ---
    app_name: str = "MedFusion AI"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    demo_users_enabled: bool = False

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
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        if self.app_env.strip().lower() not in {"prod", "production"}:
            for dev_origin in ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"]:
                if dev_origin not in origins:
                    origins.append(dev_origin)
        return origins

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
