from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import Lens, Posting
from specula_api.schemas.lens import LensCreate, LensUpdate
from specula_api.services.lens_filter import lens_where, new_predicate


async def derive_counts(session: AsyncSession, user_id: UUID, lens: Lens) -> tuple[int, int]:
    """`(count, is_new)` for a lens — DERIVED from the pool, never read from a column."""
    stmt = (
        select(func.count(), func.count().filter(new_predicate()))
        .select_from(Posting)
        .where(Posting.user_id == user_id, *lens_where(lens))
    )
    row = (await session.execute(stmt)).one()
    return int(row[0]), int(row[1])


async def _ensure_default(session: AsyncSession, user_id: UUID) -> None:
    """Every user has exactly one default 'All' lens — create it lazily if missing."""
    existing = await session.scalar(
        select(Lens).where(Lens.user_id == user_id, Lens.is_default.is_(True))
    )
    if existing is None:
        session.add(
            Lens(
                user_id=user_id,
                name="All",
                short="Everything",
                is_default=True,
                active=True,
                modes=[],
                seeds=[],
            )
        )
        await session.flush()


async def list_lenses(session: AsyncSession, user_id: UUID) -> list[tuple[Lens, int, int]]:
    await _ensure_default(session, user_id)
    lenses = (
        await session.scalars(
            select(Lens)
            .where(Lens.user_id == user_id)
            .order_by(Lens.is_default.desc(), Lens.created_at)
        )
    ).all()
    result: list[tuple[Lens, int, int]] = []
    for lens in lenses:
        count, is_new = await derive_counts(session, user_id, lens)
        result.append((lens, count, is_new))
    return result


async def get_lens(session: AsyncSession, user_id: UUID, lens_id: UUID) -> Lens | None:
    lens = await session.get(Lens, lens_id)
    if lens is None or lens.user_id != user_id:  # belt-and-suspenders alongside RLS
        return None
    return lens


async def create_lens(session: AsyncSession, user_id: UUID, data: LensCreate) -> Lens:
    lens = Lens(
        user_id=user_id,
        name=data.name,
        short=data.short,
        scope=data.scope,
        modes=data.modes,
        origin_rule=data.origin,
        focus=data.focus,
        seeds=data.seeds,
        active=data.active,
        is_default=False,
    )
    session.add(lens)
    await session.flush()
    return lens


async def update_lens(
    session: AsyncSession, user_id: UUID, lens_id: UUID, data: LensUpdate
) -> Lens | None:
    lens = await get_lens(session, user_id, lens_id)
    if lens is None:
        return None
    fields = data.model_dump(exclude_unset=True)
    if "origin" in fields:
        lens.origin_rule = fields.pop("origin")
    for field, value in fields.items():
        setattr(lens, field, value)
    await session.flush()
    return lens


async def delete_lens(session: AsyncSession, lens: Lens) -> None:
    await session.delete(lens)
    await session.flush()
