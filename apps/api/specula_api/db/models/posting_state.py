import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from specula_api.db.base import Base
from specula_api.db.columns import TimestampMixin, user_fk


class PostingState(TimestampMixin, Base):
    """User state on a posting (status, notes, feedback)."""

    __tablename__ = "posting_state"

    posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("postings.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = user_fk()
    status: Mapped[str | None] = mapped_column(Text, nullable=True)  # Saved|Applied|...|Dismissed
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    dismiss_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)  # 'positive'|'negative'|None
