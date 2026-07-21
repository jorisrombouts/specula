import uuid

from sqlalchemy import ARRAY, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from specula_api.db.base import Base
from specula_api.db.columns import Vector1536, uuid_pk


class SkillsTaxonomy(Base):
    """Canonical skill taxonomy — GLOBAL, unscoped (no user_id)."""

    __tablename__ = "skills_taxonomy"

    id: Mapped[uuid.UUID] = uuid_pk()
    canonical: Mapped[str] = mapped_column(Text, unique=True)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    vec: Mapped[list[float] | None] = mapped_column(Vector1536, nullable=True)
    # Which embedding provenance produced `vec` — vectors are only comparable within one.
    # Guards two silent failures: a recorded/test run's pseudo-vectors leaking into live
    # scoring through this GLOBAL table, and a future `openai_embed_model` change reusing
    # vectors from an incompatible space. See pipeline/score.py::_vector_provenance.
    vec_model: Mapped[str | None] = mapped_column(Text, nullable=True)
