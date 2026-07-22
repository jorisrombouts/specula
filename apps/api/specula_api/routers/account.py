from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.deps import get_current_user_id, get_session
from specula_api.schemas.account import ExportBundle
from specula_api.services.account import delete_account, export_account

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/export")
async def export_my_data(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ExportBundle:
    return await export_account(session, user_id)


@router.delete("", status_code=204)
async def delete_my_account(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await delete_account(session, user_id)
    return Response(status_code=204)
