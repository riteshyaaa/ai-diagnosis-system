"""Safety tests for the local database initialization script."""

import os
from pathlib import Path

import pytest

from scripts import init_db


def test_init_db_applies_migrations_to_local_sqlite_without_seeding(monkeypatch) -> None:
    for key in ("DATABASE_URL", "APP_ENV", "DEBUG", "DEMO_USERS_ENABLED"):
        monkeypatch.delenv(key, raising=False)

    calls = []

    def record_upgrade(config, revision):
        calls.append((config, revision))

    monkeypatch.setattr(init_db.command, "upgrade", record_upgrade)

    init_db.init_db()

    assert os.environ["DATABASE_URL"] == init_db.local_database_url()
    assert os.environ["DATABASE_URL"].startswith("sqlite+aiosqlite:///")
    assert os.environ["APP_ENV"] == "development"
    assert os.environ["DEBUG"] == "true"
    assert os.environ["DEMO_USERS_ENABLED"] == "false"
    assert len(calls) == 1

    config, revision = calls[0]
    assert revision == "head"
    assert Path(config.get_main_option("script_location")).resolve() == (
        init_db.BACKEND_ROOT / "alembic"
    ).resolve()


def test_init_db_preserves_explicit_database_url_and_requests_only_upgrade(monkeypatch) -> None:
    database_url = "sqlite+aiosqlite:///./existing-development.db"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("APP_ENV", "development")

    calls = []
    monkeypatch.setattr(
        init_db.command,
        "upgrade",
        lambda config, revision: calls.append((config, revision)),
    )

    init_db.init_db()

    assert os.environ["DATABASE_URL"] == database_url
    assert len(calls) == 1
    assert calls[0][1] == "head"


def test_init_db_refuses_production_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    calls = []
    monkeypatch.setattr(
        init_db.command,
        "upgrade",
        lambda config, revision: calls.append((config, revision)),
    )

    with pytest.raises(RuntimeError, match="not production"):
        init_db.init_db()

    assert calls == []
