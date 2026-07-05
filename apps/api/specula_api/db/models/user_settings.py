import uuid

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from specula_api.db.base import Base
from specula_api.db.columns import TimestampMixin, user_fk


class UserSettings(TimestampMixin, Base):
    """Per-user 1:1 tweaks store (not in the §4 spec DDL — added for misc per-user overrides)."""

    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = user_fk(primary_key=True)
    tweaks: Mapped[dict[str, object]] = mapped_column(JSONB, server_default=text("'{}'"))
