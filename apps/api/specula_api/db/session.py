from pgvector.asyncpg import register_vector  # type: ignore[import-untyped]
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from specula_api.config import settings

engine = create_async_engine(settings.database_url, poolclass=NullPool)
async_session = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _register_vector(dbapi_conn, _):  # type: ignore[no-untyped-def]
    dbapi_conn.run_async(register_vector)
