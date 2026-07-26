from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.config import settings
from specula_api.deps import get_current_user_id, get_session
from specula_api.schemas.discovery_settings import DiscoverySettingsIn, DiscoverySettingsOut
from specula_api.services.discovery_settings import effective_max_searches, set_max_searches

router = APIRouter(prefix="/settings/discovery", tags=["settings"])


@router.get("")
async def read_discovery_settings(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> DiscoverySettingsOut:
    return DiscoverySettingsOut(
        max_searches=await effective_max_searches(session, user_id, settings)
    )


@router.put("")
async def update_discovery_settings(
    data: DiscoverySettingsIn,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> DiscoverySettingsOut:
    value = await set_max_searches(session, user_id, data.max_searches)
    return DiscoverySettingsOut(max_searches=value)
