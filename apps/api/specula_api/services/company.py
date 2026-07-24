from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import Company, Posting
from specula_api.schemas.company import CompanyPatch


class DomainConflictError(Exception):
    """A domain edit would collide with an existing company for the same user."""


async def _open_roles(session: AsyncSession, user_id: UUID, company_id: UUID) -> int:
    # Counts are DERIVED server-side: open roles = still-open postings for the company.
    count = await session.scalar(
        select(func.count())
        .select_from(Posting)
        .where(
            Posting.user_id == user_id,
            Posting.company_id == company_id,
            Posting.still_open.is_(True),
        )
    )
    return count or 0


async def list_companies(session: AsyncSession, user_id: UUID) -> list[tuple[Company, int]]:
    open_counts = (
        select(Posting.company_id, func.count().label("n"))
        .where(Posting.user_id == user_id, Posting.still_open.is_(True))
        .group_by(Posting.company_id)
        .subquery()
    )
    stmt = (
        select(Company, func.coalesce(open_counts.c.n, 0))
        .outerjoin(open_counts, open_counts.c.company_id == Company.id)
        # opt_out is per-company "removal" (spec §15): excluded here so a removed company
        # disappears from the registry and stays gone on reload, not just skipped by ingest.
        .where(Company.user_id == user_id, Company.opt_out.is_(False))
        .order_by(Company.added_at.desc())
    )
    result = await session.execute(stmt)
    return [(company, int(n)) for company, n in result.all()]


async def patch_company(
    session: AsyncSession, user_id: UUID, company_id: UUID, data: CompanyPatch
) -> tuple[Company, int] | None:
    company = await session.get(Company, company_id)
    if company is None or company.user_id != user_id:
        return None

    updates = data.model_dump(exclude_unset=True)
    new_domain = updates.get("domain")
    if new_domain is not None and new_domain != company.domain:
        clash = await session.scalar(
            select(Company.id).where(
                Company.user_id == user_id,
                Company.domain == new_domain,
                Company.id != company_id,
            )
        )
        if clash is not None:
            raise DomainConflictError

    for field, value in updates.items():
        setattr(company, field, value)

    await session.flush()
    return company, await _open_roles(session, user_id, company_id)
