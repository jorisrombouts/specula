from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import UserSettings
from specula_api.schemas.tweaks import TweaksIn


async def get_tweaks(session: AsyncSession, user_id: UUID) -> UserSettings | None:
    return await session.get(UserSettings, user_id)


async def upsert_tweaks(session: AsyncSession, user_id: UUID, data: TweaksIn) -> UserSettings:
    settings = await session.get(UserSettings, user_id)
    if settings is None:
        settings = UserSettings(user_id=user_id)
        session.add(settings)

    settings.tweaks = data.model_dump()

    await session.flush()
    return settings
