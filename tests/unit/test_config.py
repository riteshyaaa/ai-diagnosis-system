"""Configuration validation tests."""

import pytest

from backend.app.config import Settings


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "production",
        "debug": False,
        "demo_users_enabled": False,
        "secret_key": "a" * 48,
        "database_url": "postgresql+asyncpg://medfusion:long-database-password@db.example.org:5432/medfusion",
        "cors_origins": "https://medfusion.example.org",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_valid_production_configuration_is_accepted() -> None:
    settings = production_settings()

    assert settings.app_env == "production"
    assert settings.cors_origin_list == ["https://medfusion.example.org"]


def test_empty_database_url_uses_container_database_components() -> None:
    settings = production_settings(
        database_url="",
        postgres_host="db",
        postgres_user="medfusion_service",
        postgres_password="G2$secure+database-pass",
    )

    assert settings.effective_database_url.startswith(
        "postgresql+asyncpg://medfusion_service:G2%24secure%2Bdatabase-pass@db:5432/"
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"debug": True},
        {"demo_users_enabled": True},
        {"secret_key": "CHANGE_ME_" + "a" * 40},
        {"secret_key": "short"},
        {"database_url": "sqlite+aiosqlite:///./medfusion.db"},
        {"database_url": "postgresql+asyncpg://user:password@localhost:5432/medfusion"},
        {"database_url": "postgresql+asyncpg://user:long-database-password@127.0.0.2:5432/medfusion"},
        {"database_url": "postgresql+asyncpg://medfusion_user:long-database-password@db.example.org:5432/medfusion"},
        {"database_url": "postgresql+asyncpg://user:short@db.example.org:5432/medfusion"},
        {"cors_origins": "*"},
        {"cors_origins": "http://medfusion.example.org"},
        {"cors_origins": "https://medfusion.example.org/path"},
    ],
)
def test_unsafe_production_configuration_is_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="Unsafe production configuration"):
        production_settings(**overrides)


def test_production_configuration_error_does_not_reveal_credentials() -> None:
    db_password = "Short-Secret-7"

    with pytest.raises(ValueError) as error:
        production_settings(
            database_url=f"postgresql+asyncpg://medfusion:{db_password}@db.example.org:5432/medfusion"
        )

    assert db_password not in str(error.value)


def test_development_defaults_remain_available() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.debug is True
