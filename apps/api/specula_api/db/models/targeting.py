import uuid

from sqlalchemy import ARRAY, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from specula_api.db.base import Base
from specula_api.db.columns import TimestampMixin, user_fk


class Targeting(TimestampMixin, Base):
    __tablename__ = "targeting"

    user_id: Mapped[uuid.UUID] = user_fk(primary_key=True)
    role_titles: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    seniority: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    must_haves: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    avoid: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    preferences: Mapped[str | None] = mapped_column(Text, nullable=True)
    # NOTE: no salary fields by design (product rule — salary is never a ranking/filter input).
