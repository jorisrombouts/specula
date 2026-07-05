import uuid

from sqlalchemy import ARRAY, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from specula_api.db.base import Base
from specula_api.db.columns import TimestampMixin, Vector1536, user_fk


class CandidateProfile(TimestampMixin, Base):
    __tablename__ = "candidate_profiles"

    user_id: Mapped[uuid.UUID] = user_fk(primary_key=True)
    headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_mode: Mapped[str | None] = mapped_column(Text, nullable=True)
    visa: Mapped[str | None] = mapped_column(Text, nullable=True)
    years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    education: Mapped[str | None] = mapped_column(Text, nullable=True)
    languages: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    skills: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    projects: Mapped[list[object]] = mapped_column(JSONB, server_default=text("'[]'"))
    experience: Mapped[list[object]] = mapped_column(JSONB, server_default=text("'[]'"))
    skills_vec: Mapped[list[float] | None] = mapped_column(Vector1536, nullable=True)
