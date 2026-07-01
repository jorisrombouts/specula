from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from specula_api.config import settings

engine = create_async_engine(settings.database_url, poolclass=NullPool)
async_session = async_sessionmaker(engine, expire_on_commit=False)
