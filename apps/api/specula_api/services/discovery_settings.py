from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.config import Settings
from specula_api.db.models import UserSettings

MIN_SEARCHES, MAX_SEARCHES = 1, 20


async def effective_max_searches(session: AsyncSession, user_id: UUID, settings: Settings) -> int:
    """The user's discovery search cap: their `UserSettings.discovery_max_searches` clamped to
    1..20, or the global default when they haven't set one."""
    row = await session.get(UserSettings, user_id)
    value = row.discovery_max_searches if row is not None else None
    if value is None:
        return settings.discovery_max_searches
    return max(MIN_SEARCHES, min(MAX_SEARCHES, value))


async def set_max_searches(session: AsyncSession, user_id: UUID, value: int) -> int:
    """Persist the user's discovery search cap (creating their UserSettings row if needed) and
    return the stored value. Mirrors `upsert_tweaks`."""
    row = await session.get(UserSettings, user_id)
    if row is None:
        row = UserSettings(user_id=user_id)
        session.add(row)
    row.discovery_max_searches = value
    await session.flush()
    return value
