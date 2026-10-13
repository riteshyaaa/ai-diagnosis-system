"""Migration integration tests against a disposable SQLite database."""

import os
from pathlib import Path
import subprocess
import sys
import uuid

from sqlalchemy import create_engine, text


def test_migrations_backfill_patient_owner_and_add_prediction_input_refs(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration test.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    backend_dir = Path(__file__).resolve().parents[2] / "backend"

    initial = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "001_initial_schema"],
        cwd=backend_dir,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert initial.returncode == 0, initial.stdout + initial.stderr

    user_id, second_user_id = uuid.uuid4(), uuid.uuid4()
    patient_id, ambiguous_patient_id = uuid.uuid4(), uuid.uuid4()
    sync_url = f"sqlite:///{database_path.as_posix()}"
    engine = create_engine(sync_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO users
                    (id, email, hashed_password, full_name, role, is_active,
                     is_verified, failed_login_attempts, created_at, updated_at)
                    VALUES (:id, :email, 'fixture-hash', 'Migration Test',
                            'clinician', 1, 1, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"""
                ),
                {"id": str(user_id), "email": f"{user_id}@example.test"},
            )
            connection.execute(
                text(
                    """INSERT INTO patients (id, mrn_hash, sex, created_at, updated_at)
                    VALUES (:id, :mrn, 'female', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"""
                ),
                {"id": str(patient_id), "mrn": "m" * 64},
            )
            connection.execute(
                text(
                    """INSERT INTO users
                    (id, email, hashed_password, full_name, role, is_active,
                     is_verified, failed_login_attempts, created_at, updated_at)
                    VALUES (:id, :email, 'fixture-hash', 'Second User',
                            'clinician', 1, 1, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"""
                ),
                {"id": str(second_user_id), "email": f"{second_user_id}@example.test"},
            )
            connection.execute(
                text(
                    """INSERT INTO patients (id, mrn_hash, sex, created_at, updated_at)
                    VALUES (:id, :mrn, 'male', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"""
                ),
                {"id": str(ambiguous_patient_id), "mrn": "n" * 64},
            )
            connection.execute(
                text(
                    """INSERT INTO audit_logs
                    (id, user_id, action, resource_type, resource_id, timestamp)
                    VALUES (:id, :user_id, 'patient_create', 'patient', :resource_id,
                            CURRENT_TIMESTAMP)"""
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": str(user_id),
                    "resource_id": str(patient_id),
                },
            )
            connection.execute(
                text(
                    """INSERT INTO audit_logs
                    (id, user_id, action, resource_type, resource_id, timestamp)
                    VALUES (:id, :user_id, 'patient_create', 'patient', :resource_id,
                            CURRENT_TIMESTAMP)"""
                ),
                [
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": str(user_id),
                        "resource_id": str(ambiguous_patient_id),
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": str(second_user_id),
                        "resource_id": str(ambiguous_patient_id),
                    },
                ],
            )

        upgraded = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=backend_dir,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr

        with engine.connect() as connection:
            owner_id = connection.execute(
                text("SELECT created_by_id FROM patients WHERE id = :id"),
                {"id": str(patient_id)},
            ).scalar_one()
            ambiguous_owner_id = connection.execute(
                text("SELECT created_by_id FROM patients WHERE id = :id"),
                {"id": str(ambiguous_patient_id)},
            ).scalar_one()
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            prediction_columns = {
                row["name"]
                for row in connection.execute(
                    text("PRAGMA table_info(prediction_records)")
                ).mappings()
            }

        assert owner_id == str(user_id)
        assert ambiguous_owner_id is None
        assert revision == "003_prediction_input_refs"
        assert {
            "image_record_id",
            "clinical_record_id",
            "image_file_hash",
            "clinical_record_updated_at",
        }.issubset(prediction_columns)
    finally:
        engine.dispose()
