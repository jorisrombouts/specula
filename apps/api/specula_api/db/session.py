from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from pgvector.asyncpg import register_vector  # type: ignore[import-untyped]
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from specula_api.config import settings

engine = create_async_engine(settings.database_url, poolclass=NullPool)
async_session = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _register_vector(dbapi_conn, _):  # type: ignore[no-untyped-def]
    dbapi_conn.run_async(register_vector)


@asynccontextmanager
async def tenant_session(user_id: UUID) -> AsyncIterator[AsyncSession]:
    """The ONLY sanctioned way off-request code (BackgroundTasks / CLI) opens a session:
    sets the app.user_id GUC so RLS is enforced, commits on success, rolls back on error.
    Off-request work has no get_session dependency, so it must set the GUC itself or RLS
    fails closed (reads return [], writes raise WITH CHECK)."""
    async with async_session() as session:
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(user_id))
        )
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
