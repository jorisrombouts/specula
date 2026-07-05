import uuid
from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from specula_api.db.base import Base
from specula_api.db.columns import Vector1536, user_fk, uuid_pk


class Posting(Base):
    __tablename__ = "postings"
    __table_args__ = (UniqueConstraint("user_id", "content_hash"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    # extracted insight record (LLM, schema-validated):
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    role_family: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    hq_country: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_mode: Mapped[str | None] = mapped_column(Text, nullable=True)
    seniority: Mapped[str | None] = mapped_column(Text, nullable=True)
    education: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_skills: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    nice_to_have: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    visa: Mapped[str | None] = mapped_column(Text, nullable=True)
    languages: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    contract: Mapped[str | None] = mapped_column(Text, nullable=True)
    geo: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # only if stated
    deadline_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    posted_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    responsibilities: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    still_open: Mapped[bool | None] = mapped_column(Boolean, server_default=text("true"))
    extraction_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title_vec: Mapped[list[float] | None] = mapped_column(Vector1536, nullable=True)
    skills_vec: Mapped[list[float] | None] = mapped_column(Vector1536, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    dedup_group: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # NOTE: no raw_snapshot_key — no object storage (product deviation); content_hash +
    # source_url are the provenance/dedup surface.
