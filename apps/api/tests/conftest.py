import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from specula_api.db import models  # noqa: F401  (register models on Base.metadata)
from specula_api.db.models import User
from specula_api.db.session import engine


@pytest.fixture(scope="session")
def migrated_db() -> None:
    command.upgrade(Config("alembic.ini"), "head")


@pytest_asyncio.fixture
async def db_session(migrated_db: None) -> AsyncGenerator[AsyncSession, None]:
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


async def set_tenant(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(user_id))
    )


async def make_user(session: AsyncSession) -> User:
    u = User(email=f"{uuid.uuid4()}@example.com", google_sub=str(uuid.uuid4()))
    session.add(u)
    await session.flush()
    return u
