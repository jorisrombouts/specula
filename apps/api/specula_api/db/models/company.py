import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from specula_api.db.base import Base
from specula_api.db.columns import user_fk, uuid_pk


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("user_id", "domain"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    name: Mapped[str] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ats: Mapped[str | None] = mapped_column(Text, nullable=True)
    careers_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    hq_country: Mapped[str | None] = mapped_column(Text, nullable=True)
    hq_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comp_estimate: Mapped[str | None] = mapped_column(Text, nullable=True)
    tracking: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    opt_out: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'approved'"))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
