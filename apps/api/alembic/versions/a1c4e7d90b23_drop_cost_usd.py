"""drop cost_usd — Specula meters tokens, not cost

Destructive and irreversible: historical spend is discarded. The downgrade recreates the
columns with their original defaults, but the original values are unrecoverable. Accepted
deliberately on 2026-07-29 alongside the removal of the USD budget guard.

Revision ID: a1c4e7d90b23
Revises: d3f7a1c9e2b4
Create Date: 2026-07-29 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1c4e7d90b23"
down_revision: str | Sequence[str] | None = "d3f7a1c9e2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("llm_costs", "cost_usd")
    op.drop_column("runs", "cost_usd")


def downgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True),
    )
    op.add_column(
        "llm_costs",
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
    )
