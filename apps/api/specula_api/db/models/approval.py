import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from specula_api.db.base import Base
from specula_api.db.columns import user_fk, uuid_pk


class Approval(Base):
    """Approval queue: candidate companies awaiting decision."""

    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The URL discovery actually found. `domain` is fabricated for path-token ATSes
    # (acme.boards.greenhouse.io) and does not resolve, so this is the only address enrich can
    # fetch a real page from — without it the model guesses every field from the name.
    careers_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ats: Mapped[str | None] = mapped_column(Text, nullable=True)
    hq_country: Mapped[str | None] = mapped_column(Text, nullable=True)
    found_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    why: Mapped[str | None] = mapped_column(Text, nullable=True)
    open_roles: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    hq_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)  # approve|reject|snooze
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
