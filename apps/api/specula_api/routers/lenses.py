from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import Lens
from specula_api.deps import get_current_user_id, get_session
from specula_api.schemas.lens import LensCreate, LensSummaryOut, LensUpdate
from specula_api.services.lenses import (
    create_lens,
    delete_lens,
    derive_counts,
    get_lens,
    list_lenses,
    update_lens,
)

router = APIRouter(prefix="/lenses", tags=["lenses"])


def _summary(lens: Lens, count: int, is_new: int) -> LensSummaryOut:
    # `origin` ← `origin_rule`; nullable columns coerced to "" to match the TS contract.
    return LensSummaryOut(
        id=lens.id,
        name=lens.name,
        short=lens.short or "",
        active=lens.active,
        scope=lens.scope or "",
        modes=lens.modes,
        origin=lens.origin_rule or "",
        focus=lens.focus or "",
        seeds=lens.seeds,
        count=count,
        is_new=is_new,
        is_default=lens.is_default,
    )


@router.get("")
async def read_lenses(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[LensSummaryOut]:
    rows = await list_lenses(session, user_id)
    return [_summary(lens, count, is_new) for lens, count, is_new in rows]


@router.post("", status_code=201)
async def add_lens(
    data: LensCreate,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> LensSummaryOut:
    lens = await create_lens(session, user_id, data)
    count, is_new = await derive_counts(session, user_id, lens)
    return _summary(lens, count, is_new)


@router.patch("/{lens_id}")
async def edit_lens(
    lens_id: UUID,
    data: LensUpdate,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> LensSummaryOut:
    lens = await update_lens(session, user_id, lens_id, data)
    if lens is None:
        raise HTTPException(status_code=404, detail="Lens not found")
    count, is_new = await derive_counts(session, user_id, lens)
    return _summary(lens, count, is_new)


@router.delete("/{lens_id}", status_code=204)
async def remove_lens(
    lens_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> Response:
    lens = await get_lens(session, user_id, lens_id)
    if lens is None:
        raise HTTPException(status_code=404, detail="Lens not found")
    if lens.is_default:
        raise HTTPException(status_code=409, detail="The default lens cannot be deleted")
    await delete_lens(session, lens)
    return Response(status_code=204)
