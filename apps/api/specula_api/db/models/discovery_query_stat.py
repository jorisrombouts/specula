import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from specula_api.db.base import Base
from specula_api.db.columns import TimestampMixin, user_fk


class DiscoveryQueryStat(TimestampMixin, Base):
    """Per-user memory of how a discovery query has been performing, so played-out searches (all
    their companies already known) get parked instead of re-paid every run. PK is (user_id,
    query); the exhaustion filter reads consecutive_empty_runs + last_run_at."""

    __tablename__ = "discovery_query_stat"

    user_id: Mapped[uuid.UUID] = user_fk(primary_key=True)
    query: Mapped[str] = mapped_column(Text, primary_key=True)
    last_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consecutive_empty_runs: Mapped[int] = mapped_column(Integer, server_default=text("0"))
