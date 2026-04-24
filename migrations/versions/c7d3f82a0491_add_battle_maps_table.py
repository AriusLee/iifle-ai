"""add battle_maps table for Phase 1.5

Revision ID: c7d3f82a0491
Revises: b1c2d3e4f5a6
Create Date: 2026-04-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c7d3f82a0491"
down_revision: str = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extend reporttype enum so we can persist battle map reports alongside
    # diagnostic reports in the shared reports table.
    op.execute("ALTER TYPE reporttype ADD VALUE IF NOT EXISTS 'battle_map'")

    battle_map_status = sa.Enum(
        "draft", "submitted", "classifying", "generating", "completed", "failed",
        name="battlemapstatus",
    )
    battle_map_variant = sa.Enum(
        "replication", "financing", "capitalization",
        name="battlemapvariant",
    )

    op.create_table(
        "battle_maps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("diagnostic_id", sa.Uuid(), nullable=False),
        sa.Column("status", battle_map_status, nullable=False, server_default="draft"),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("other_answers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("variant", battle_map_variant, nullable=True),
        sa.Column("current_stage", sa.String(length=100), nullable=True),
        sa.Column("target_stage", sa.String(length=100), nullable=True),
        sa.Column("headline_verdict_zh", sa.Text(), nullable=True),
        sa.Column("headline_verdict_en", sa.Text(), nullable=True),
        sa.Column("top_priorities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("do_not_do", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("battle_modules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("timeline", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("report_id", sa.Uuid(), nullable=True),
        sa.Column("progress_message", sa.String(length=200), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["diagnostic_id"], ["diagnostics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_battle_maps_company_id", "battle_maps", ["company_id"])
    op.create_index("ix_battle_maps_user_id", "battle_maps", ["user_id"])
    op.create_index("ix_battle_maps_diagnostic_id", "battle_maps", ["diagnostic_id"])
    op.create_index("ix_battle_maps_status", "battle_maps", ["status"])


def downgrade() -> None:
    op.drop_index("ix_battle_maps_status", table_name="battle_maps")
    op.drop_index("ix_battle_maps_diagnostic_id", table_name="battle_maps")
    op.drop_index("ix_battle_maps_user_id", table_name="battle_maps")
    op.drop_index("ix_battle_maps_company_id", table_name="battle_maps")
    op.drop_table("battle_maps")
    op.execute("DROP TYPE IF EXISTS battlemapvariant")
    op.execute("DROP TYPE IF EXISTS battlemapstatus")
    # Note: postgres does not support removing enum values without recreating
    # the type, so we leave 'battle_map' on reporttype on downgrade.
