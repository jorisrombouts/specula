"""add skills_taxonomy.vec_model (embedding provenance)

Cached skill vectors are only interchangeable with vectors produced by the SAME embedding
model. Without provenance, two things go silently wrong: a recorded/test run writes
deterministic pseudo-vectors into this GLOBAL table and live scoring then reuses them
(cosines collapse to noise), and changing `openai_embed_model` would reuse vectors from an
incompatible space forever. Recording which model produced each vector makes the cache
self-invalidating on both counts — a row whose `vec_model` doesn't match the current
provenance is simply re-embedded.

Existing rows get NULL, which never matches a provenance string, so any already-poisoned
vector is ignored and refilled on next use.

Revision ID: b7d41e05a9c2
Revises: 2366c297858b
"""

import sqlalchemy as sa

from alembic import op

revision = "b7d41e05a9c2"
down_revision = "2366c297858b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("skills_taxonomy", sa.Column("vec_model", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("skills_taxonomy", "vec_model")
