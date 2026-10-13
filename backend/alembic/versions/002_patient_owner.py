"""Add explicit patient ownership and backfill from creation audit events."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002_patient_owner"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("patients") as batch_op:
        batch_op.add_column(
            sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_patients_created_by_id_users",
            "users",
            ["created_by_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_index("ix_patients_created_by_id", "patients", ["created_by_id"])

    # Assign legacy patients only when their create events name one distinct
    # actor. Ambiguous or missing audit history stays NULL and fails closed.
    op.execute(
        sa.text(
            """
            WITH unique_owners AS (
                SELECT lower(replace(audit_logs.resource_id, '-', '')) AS patient_key
                FROM audit_logs
                WHERE lower(CAST(audit_logs.action AS VARCHAR)) = 'patient_create'
                  AND lower(CAST(audit_logs.resource_type AS VARCHAR)) = 'patient'
                  AND audit_logs.user_id IS NOT NULL
                  AND audit_logs.resource_id IS NOT NULL
                GROUP BY lower(replace(audit_logs.resource_id, '-', ''))
                HAVING COUNT(DISTINCT audit_logs.user_id) = 1
            )
            UPDATE patients
            SET created_by_id = (
                SELECT audit_logs.user_id
                FROM audit_logs
                JOIN unique_owners
                  ON unique_owners.patient_key =
                     lower(replace(audit_logs.resource_id, '-', ''))
                WHERE lower(CAST(audit_logs.action AS VARCHAR)) = 'patient_create'
                  AND lower(CAST(audit_logs.resource_type AS VARCHAR)) = 'patient'
                  AND audit_logs.user_id IS NOT NULL
                  AND audit_logs.resource_id IS NOT NULL
                  AND lower(replace(audit_logs.resource_id, '-', '')) =
                      lower(replace(CAST(patients.id AS VARCHAR), '-', ''))
                ORDER BY audit_logs.timestamp ASC
                LIMIT 1
            )
            WHERE patients.created_by_id IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_patients_created_by_id", table_name="patients")
    with op.batch_alter_table("patients") as batch_op:
        batch_op.drop_constraint("fk_patients_created_by_id_users", type_="foreignkey")
        batch_op.drop_column("created_by_id")
