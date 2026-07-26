"""cheaper discovery: per-user search cap + query-exhaustion stats

Adds `user_settings.discovery_max_searches` (nullable per-user override of the global cap) and
the `discovery_query_stat` table (RLS-forced) that drives the exhaustion cache.

Revision ID: d3f7a1c9e2b4
Revises: c8f1a2b3d4e5
Create Date: 2026-07-26 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d3f7a1c9e2b4"
down_revision: str | Sequence[str] | None = "c8f1a2b3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user_settings",
        sa.Column("discovery_max_searches", sa.Integer(), nullable=True),
    )
    op.create_table(
        "discovery_query_stat",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "consecutive_empty_runs", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "query"),
    )
    tenant = "nullif(current_setting('app.user_id', true), '')::uuid"
    op.execute("ALTER TABLE discovery_query_stat ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE discovery_query_stat FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON discovery_query_stat "
        f"USING (user_id = {tenant}) WITH CHECK (user_id = {tenant})"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("discovery_query_stat")
    op.drop_column("user_settings", "discovery_max_searches")
