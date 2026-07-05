from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.deps import get_current_user_id, get_session
from specula_api.schemas.targeting import TargetingIn, TargetingOut
from specula_api.services.targeting import get_targeting, upsert_targeting

router = APIRouter(prefix="/targeting", tags=["targeting"])


@router.get("")
async def read_targeting(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> TargetingOut:
    targeting = await get_targeting(session, user_id)
    if targeting is None:
        return TargetingOut(updated_at=datetime.now(UTC))
    return TargetingOut.model_validate(targeting)


@router.put("")
async def replace_targeting(
    data: TargetingIn,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> TargetingOut:
    targeting = await upsert_targeting(session, user_id, data)
    return TargetingOut.model_validate(targeting)
