"""m5 hardening foundation

Adds the M5 cost-ledger table (`llm_costs`, RLS-forced tenant-isolated), a per-company
`opt_out` removal flag, and `runs.cost_usd`/`runs.duration_ms` rollups.

Revision ID: 5f2f2fb3a1af
Revises: b7d41e05a9c2
Create Date: 2026-07-22 12:53:56.162102

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5f2f2fb3a1af"
down_revision: str | Sequence[str] | None = "b7d41e05a9c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "llm_costs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("company_id", sa.UUID(), nullable=True),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("embed_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_llm_costs_user_id"), "llm_costs", ["user_id"], unique=False)

    tenant = "nullif(current_setting('app.user_id', true), '')::uuid"
    op.execute("ALTER TABLE llm_costs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE llm_costs FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON llm_costs "
        f"USING (user_id = {tenant}) WITH CHECK (user_id = {tenant})"
    )

    op.add_column(
        "companies",
        sa.Column("opt_out", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("runs", sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True))
    op.add_column("runs", sa.Column("duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("runs", "duration_ms")
    op.drop_column("runs", "cost_usd")
    op.drop_column("companies", "opt_out")
    op.drop_index(op.f("ix_llm_costs_user_id"), table_name="llm_costs")
    op.drop_table("llm_costs")  # policy drops with the table
