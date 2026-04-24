"""add section_analyses column to battle_maps

Revision ID: d8a91b4f2c10
Revises: c7d3f82a0491
Create Date: 2026-04-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d8a91b4f2c10"
down_revision: str = "c7d3f82a0491"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "battle_maps",
        sa.Column(
            "section_analyses",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("battle_maps", "section_analyses")
