"""initial_schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-09-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "clinician", "radiologist", "auditor", name="user_role"),
            nullable=False,
        ),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)
    op.create_index(op.f("ix_users_created_at"), "users", ["created_at"], unique=False)

    # 2. patients table
    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mrn_hash", sa.String(length=64), nullable=False),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column(
            "sex",
            sa.Enum("male", "female", "other", "unknown", name="biological_sex"),
            nullable=False,
        ),
        sa.Column("blood_group", sa.String(length=10), nullable=True),
        sa.Column("medical_history_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_patients_mrn_hash"), "patients", ["mrn_hash"], unique=True)
    op.create_index(op.f("ix_patients_created_at"), "patients", ["created_at"], unique=False)

    # 3. diagnostic_cases table
    op.create_table(
        "diagnostic_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_number", sa.String(length=50), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "modality",
            sa.Enum("image_only", "tabular_only", "multimodal", name="case_modality"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("draft", "submitted", "processing", "completed", "reviewed", "archived", name="case_status"),
            nullable=False,
        ),
        sa.Column("chief_complaint", sa.String(length=500), nullable=True),
        sa.Column("clinical_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_diagnostic_cases_case_number"), "diagnostic_cases", ["case_number"], unique=True)
    op.create_index(op.f("ix_diagnostic_cases_patient_id"), "diagnostic_cases", ["patient_id"], unique=False)
    op.create_index(op.f("ix_diagnostic_cases_created_by_id"), "diagnostic_cases", ["created_by_id"], unique=False)
    op.create_index(op.f("ix_diagnostic_cases_status"), "diagnostic_cases", ["status"], unique=False)
    op.create_index(op.f("ix_diagnostic_cases_created_at"), "diagnostic_cases", ["created_at"], unique=False)

    # 4. image_records table
    op.create_table(
        "image_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(length=50), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "image_type",
            sa.Enum("chest_xray_pa", "chest_xray_ap", "chest_xray_lateral", "other", name="image_type"),
            nullable=False,
        ),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("channels", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["diagnostic_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_image_records_case_id"), "image_records", ["case_id"], unique=False)
    op.create_index(op.f("ix_image_records_created_at"), "image_records", ["created_at"], unique=False)

    # 5. clinical_records table
    op.create_table(
        "clinical_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recorded_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("sex", sa.Integer(), nullable=False),
        sa.Column("chest_pain_type", sa.Integer(), nullable=False),
        sa.Column("resting_bp", sa.Float(), nullable=False),
        sa.Column("cholesterol", sa.Float(), nullable=False),
        sa.Column("fasting_bs", sa.Integer(), nullable=False),
        sa.Column("resting_ecg", sa.Integer(), nullable=False),
        sa.Column("max_hr", sa.Float(), nullable=False),
        sa.Column("exercise_angina", sa.Integer(), nullable=False),
        sa.Column("st_depression", sa.Float(), nullable=False),
        sa.Column("st_slope", sa.Integer(), nullable=False),
        sa.Column("num_major_vessels", sa.Integer(), nullable=False),
        sa.Column("thalassemia", sa.Integer(), nullable=False),
        sa.Column("bmi", sa.Float(), nullable=True),
        sa.Column("smoking_status", sa.String(length=50), nullable=True),
        sa.Column("raw_metrics", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["diagnostic_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clinical_records_case_id"), "clinical_records", ["case_id"], unique=False)
    op.create_index(op.f("ix_clinical_records_created_at"), "clinical_records", ["created_at"], unique=False)

    # 6. prediction_records table
    op.create_table(
        "prediction_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "model_type",
            sa.Enum(
                "image_densenet121",
                "image_efficientnet_b0",
                "tabular_xgboost",
                "tabular_logistic_regression",
                "tabular_random_forest",
                "multimodal_fusion",
                name="model_type",
            ),
            nullable=False,
        ),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("primary_condition", sa.String(length=100), nullable=False),
        sa.Column("raw_probability", sa.Float(), nullable=False),
        sa.Column("calibrated_probability", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column(
            "confidence_band",
            sa.Enum("high", "moderate", "low", name="confidence_band"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("confident", "uncertain", "abstained", name="prediction_status"),
            nullable=False,
        ),
        sa.Column("abstention_reason", sa.String(length=255), nullable=True),
        sa.Column("detailed_predictions", sa.JSON(), nullable=False),
        sa.Column("inference_latency_ms", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["diagnostic_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_prediction_records_case_id"), "prediction_records", ["case_id"], unique=False)
    op.create_index(op.f("ix_prediction_records_confidence_band"), "prediction_records", ["confidence_band"], unique=False)
    op.create_index(op.f("ix_prediction_records_created_at"), "prediction_records", ["created_at"], unique=False)

    # 7. explanation_records table
    op.create_table(
        "explanation_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prediction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "explanation_type",
            sa.Enum("gradcam_saliency", "shap_feature_importance", "multimodal_attribution", name="explanation_type"),
            nullable=False,
        ),
        sa.Column("heatmap_path", sa.String(length=500), nullable=True),
        sa.Column("shap_values", sa.JSON(), nullable=True),
        sa.Column("top_features", sa.JSON(), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["prediction_id"], ["prediction_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_explanation_records_prediction_id"), "explanation_records", ["prediction_id"], unique=True)
    op.create_index(op.f("ix_explanation_records_created_at"), "explanation_records", ["created_at"], unique=False)

    # 8. clinical_reviews table
    op.create_table(
        "clinical_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prediction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "decision",
            sa.Enum("accept", "modify", "reject", name="review_decision"),
            nullable=False,
        ),
        sa.Column("modified_diagnosis", sa.String(length=255), nullable=True),
        sa.Column("clinical_notes", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["diagnostic_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prediction_id"], ["prediction_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clinical_reviews_case_id"), "clinical_reviews", ["case_id"], unique=False)
    op.create_index(op.f("ix_clinical_reviews_prediction_id"), "clinical_reviews", ["prediction_id"], unique=False)
    op.create_index(op.f("ix_clinical_reviews_reviewer_id"), "clinical_reviews", ["reviewer_id"], unique=False)
    op.create_index(op.f("ix_clinical_reviews_decision"), "clinical_reviews", ["decision"], unique=False)
    op.create_index(op.f("ix_clinical_reviews_created_at"), "clinical_reviews", ["created_at"], unique=False)

    # 9. audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "action",
            sa.Enum(
                "user_login", "user_logout", "user_login_failed", "user_locked",
                "user_register", "user_update", "user_password_change",
                "patient_create", "patient_view", "patient_update",
                "case_create", "case_view", "case_update", "case_delete",
                "image_upload", "image_view", "clinical_record_create",
                "inference_run", "explanation_generate", "review_submit",
                "report_export_pdf", "data_export", "system_config_change",
                name="audit_action",
            ),
            nullable=False,
        ),
        sa.Column(
            "resource_type",
            sa.Enum(
                "user", "patient", "case", "image", "clinical_record",
                "prediction", "review", "system",
                name="audit_resource_type",
            ),
            nullable=False,
        ),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_resource_type"), "audit_logs", ["resource_type"], unique=False)
    op.create_index(op.f("ix_audit_logs_resource_id"), "audit_logs", ["resource_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_timestamp"), "audit_logs", ["timestamp"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.execute("DROP TYPE IF EXISTS audit_resource_type;")
    op.execute("DROP TYPE IF EXISTS audit_action;")

    op.drop_table("clinical_reviews")
    op.execute("DROP TYPE IF EXISTS review_decision;")

    op.drop_table("explanation_records")
    op.execute("DROP TYPE IF EXISTS explanation_type;")

    op.drop_table("prediction_records")
    op.execute("DROP TYPE IF EXISTS prediction_status;")
    op.execute("DROP TYPE IF EXISTS confidence_band;")
    op.execute("DROP TYPE IF EXISTS model_type;")

    op.drop_table("clinical_records")

    op.drop_table("image_records")
    op.execute("DROP TYPE IF EXISTS image_type;")

    op.drop_table("diagnostic_cases")
    op.execute("DROP TYPE IF EXISTS case_status;")
    op.execute("DROP TYPE IF EXISTS case_modality;")

    op.drop_table("patients")
    op.execute("DROP TYPE IF EXISTS biological_sex;")

    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS user_role;")
