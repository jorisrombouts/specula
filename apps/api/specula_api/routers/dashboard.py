from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.deps import get_current_user_id, get_session
from specula_api.schemas.dashboard import DashboardSummary
from specula_api.services.dashboard import compute_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def read_dashboard(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> DashboardSummary:
    return await compute_dashboard(session, user_id)
