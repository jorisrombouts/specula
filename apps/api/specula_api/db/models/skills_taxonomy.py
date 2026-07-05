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
