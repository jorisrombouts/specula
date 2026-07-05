import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import ForeignKey, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

Vector1536 = Vector(1536)


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def user_fk(*, primary_key: bool = False, index: bool = True) -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=primary_key,
        index=index and not primary_key,
    )


class TimestampMixin:
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
