import asyncio
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from specula_api.db.models import User
from specula_api.db.session import async_session, engine


def _db_reachable() -> bool:
    async def check() -> bool:
        try:
            async with engine.connect():
                return True
        except Exception:
            return False

    try:
        return asyncio.run(check())
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_reachable(), reason="Postgres not reachable (run `just up`)"
)


@requires_db
def test_migration_creates_users_table(migrated_db: None) -> None:
    async def check() -> str | None:
        async with engine.connect() as conn:
            result = await conn.execute(sa.text("select to_regclass('public.users')"))
            value = result.scalar()
            return str(value) if value is not None else None

    assert asyncio.run(check()) == "users"


@requires_db
def test_user_round_trip(migrated_db: None) -> None:
    async def run() -> None:
        async with async_session() as session:
            user = User(
                email=f"{uuid.uuid4()}@example.com",
                google_sub=str(uuid.uuid4()),
                name="Test User",
            )
            session.add(user)
            await session.flush()
            fetched = await session.get(User, user.id)
            assert fetched is not None
            assert fetched.name == "Test User"
            await session.rollback()

    asyncio.run(run())


@requires_db
def test_duplicate_email_violates_unique(migrated_db: None) -> None:
    async def run() -> None:
        shared = f"{uuid.uuid4()}@example.com"
        async with async_session() as session:
            session.add(User(email=shared, google_sub=str(uuid.uuid4())))
            session.add(User(email=shared, google_sub=str(uuid.uuid4())))
            try:
                await session.flush()
                raise AssertionError("expected IntegrityError on duplicate email")
            except IntegrityError:
                await session.rollback()

    asyncio.run(run())
