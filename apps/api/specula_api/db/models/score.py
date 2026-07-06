import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from specula_api.db.base import Base
from specula_api.db.columns import user_fk


class Score(Base):
    """Lens-independent score facts, persisted per posting. `factor_loc` and the overall
    `match` index are lens-aware and computed at read time — never stored here."""

    __tablename__ = "scores"

    posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("postings.id", ondelete="CASCADE"), primary_key=True
    )
    # SERVICE OBLIGATION: `user_id` must equal the owning posting's `user_id`. It's
    # carried here (rather than joined) so the RLS policy can scope by it, but no DB
    # constraint enforces the match — always set it from the posting you're scoring,
    # never from client input.
    user_id: Mapped[uuid.UUID] = user_fk()
    factor_role: Mapped[int] = mapped_column(Integer)
    factor_skill: Mapped[int] = mapped_column(Integer)
    overlap_matched: Mapped[int] = mapped_column(Integer)
    overlap_total: Mapped[int] = mapped_column(Integer)
    red_flag: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str] = mapped_column(Text)
    scored_with: Mapped[str] = mapped_column(Text)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
