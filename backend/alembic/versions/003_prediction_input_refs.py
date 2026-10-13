"""Link inference records to the exact image and clinical-record versions."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "003_prediction_input_refs"
down_revision: str | None = "002_patient_owner"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("prediction_records") as batch_op:
        batch_op.add_column(
            sa.Column("image_record_id", postgresql.UUID(as_uuid=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("clinical_record_id", postgresql.UUID(as_uuid=True), nullable=True)
        )
        batch_op.add_column(sa.Column("image_file_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("clinical_record_updated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_prediction_records_image_record_id",
            "image_records",
            ["image_record_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_prediction_records_clinical_record_id",
            "clinical_records",
            ["clinical_record_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_index(
        "ix_prediction_records_image_record_id",
        "prediction_records",
        ["image_record_id"],
    )
    op.create_index(
        "ix_prediction_records_clinical_record_id",
        "prediction_records",
        ["clinical_record_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_prediction_records_clinical_record_id", table_name="prediction_records")
    op.drop_index("ix_prediction_records_image_record_id", table_name="prediction_records")
    with op.batch_alter_table("prediction_records") as batch_op:
        batch_op.drop_constraint("fk_prediction_records_clinical_record_id", type_="foreignkey")
        batch_op.drop_constraint("fk_prediction_records_image_record_id", type_="foreignkey")
        batch_op.drop_column("clinical_record_updated_at")
        batch_op.drop_column("image_file_hash")
        batch_op.drop_column("clinical_record_id")
        batch_op.drop_column("image_record_id")
