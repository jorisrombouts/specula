"""add approvals.careers_url

Revision ID: 2366c297858b
Revises: e0268b92bdf3
Create Date: 2026-07-21 14:05:26.579938

Carries the URL discovery actually found through to the company. `approvals.domain` is
fabricated for path-token ATSes (acme.boards.greenhouse.io) and does not resolve, so without
this the enrich stage had no real page to fetch.

Autogenerate additionally proposed dropping `ix_approvals_user_id_undecided` (partial) and
`ix_postings_skills_vec` (ivfflat) — it cannot round-trip either index kind, and both are
load-bearing. Those drops are deliberately omitted; this migration only touches the column.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2366c297858b"
down_revision: str | Sequence[str] | None = "e0268b92bdf3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("approvals", sa.Column("careers_url", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("approvals", "careers_url")
