import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from specula_api.db.base import Base
from specula_api.db.columns import user_fk, uuid_pk


class LlmCost(Base):
    """Per-call OpenAI spend ledger. Written by the pipeline (OBS), read by the
    dashboard (DASH). run_id/company_id are informational (no FK): company ingest —
    the dominant spend — creates no Run, so cost cannot hang off `runs`. Tenancy is
    the user_id FK (CASCADE) alone; account deletion drops these rows."""

    __tablename__ = "llm_costs"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    run_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    stage: Mapped[str] = mapped_column(Text)  # 'discovery'|'extract'|'embed'|'score'|'rationale'
    model: Mapped[str] = mapped_column(Text)
    prompt_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    completion_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    embed_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
