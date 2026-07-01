from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from specula_api.config import settings

engine = create_async_engine(settings.database_url)
async_session = async_sessionmaker(engine, expire_on_commit=False)
