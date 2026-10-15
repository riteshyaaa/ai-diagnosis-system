#!/usr/bin/env python3
"""Initialize the local development database using reviewed Alembic migrations.

This script never creates users or sample patient records, resets credentials,
drops tables, or stamps a database without applying its migrations.
"""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"


def local_database_url() -> str:
    """Return a stable SQLite URL for the disposable local development database."""
    database_path = (PROJECT_ROOT / "medfusion-dev.db").as_posix()
    return f"sqlite+aiosqlite:///{database_path}"


def init_db() -> None:
    """Apply pending migrations to the configured development database."""
    os.environ.setdefault("DATABASE_URL", local_database_url())
    os.environ.setdefault("APP_ENV", "development")
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault("DEMO_USERS_ENABLED", "false")

    if os.environ.get("APP_ENV", "").strip().lower() in {"prod", "production"}:
        raise RuntimeError("scripts/init_db.py is for local development, not production.")

    alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.upgrade(alembic_config, "head")
    print("Alembic migrations applied to the configured development database.")
    print("No demo accounts or sample patient records were created.")


if __name__ == "__main__":
    init_db()
