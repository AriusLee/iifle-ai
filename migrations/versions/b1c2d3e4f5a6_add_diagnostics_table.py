"""add diagnostics table

Revision ID: b1c2d3e4f5a6
Revises: a45a407f0458
Create Date: 2026-03-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: str = "9f38b1b8c0d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make assessment_id nullable on reports (diagnostics don't need assessments)
    op.alter_column("reports", "assessment_id", existing_type=sa.Uuid(), nullable=True)

    # Add 'diagnostic' to reporttype enum
    op.execute("ALTER TYPE reporttype ADD VALUE IF NOT EXISTS 'diagnostic'")

    op.create_table(
        "diagnostics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "submitted", "scoring", "completed", "failed", name="diagnosticstatus"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("other_answers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("overall_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("overall_rating", sa.String(length=50), nullable=True),
        sa.Column("enterprise_stage", sa.String(length=100), nullable=True),
        sa.Column("capital_readiness", sa.String(length=20), nullable=True),
        sa.Column("module_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("key_findings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("report_id", sa.Uuid(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("progress_message", sa.String(length=200), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diagnostics_company_id", "diagnostics", ["company_id"])
    op.create_index("ix_diagnostics_user_id", "diagnostics", ["user_id"])
    op.create_index("ix_diagnostics_status", "diagnostics", ["status"])


def downgrade() -> None:
    op.drop_index("ix_diagnostics_status", table_name="diagnostics")
    op.drop_index("ix_diagnostics_user_id", table_name="diagnostics")
    op.drop_index("ix_diagnostics_company_id", table_name="diagnostics")
    op.drop_table("diagnostics")
    op.execute("DROP TYPE IF EXISTS diagnosticstatus")
