from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.deps import get_current_user_id, get_session
from specula_api.schemas.tweaks import TweaksIn, TweaksOut
from specula_api.services.tweaks import get_tweaks, upsert_tweaks

router = APIRouter(prefix="/tweaks", tags=["tweaks"])


@router.get("")
async def read_tweaks(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> TweaksOut:
    settings = await get_tweaks(session, user_id)
    if settings is None:
        return TweaksOut()
    return TweaksOut.model_validate(settings.tweaks)


@router.put("")
async def replace_tweaks(
    data: TweaksIn,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> TweaksOut:
    settings = await upsert_tweaks(session, user_id, data)
    return TweaksOut.model_validate(settings.tweaks)
