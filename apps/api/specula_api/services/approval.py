from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import Approval, Company


async def get_undecided_approvals(session: AsyncSession, user_id: UUID) -> list[Approval]:
    result = await session.scalars(
        select(Approval)
        .where(Approval.user_id == user_id, Approval.decision.is_(None))
        .order_by(Approval.created_at)
    )
    return list(result)


async def apply_decision(
    session: AsyncSession, user_id: UUID, approval_id: UUID, decision: str
) -> tuple[Approval, UUID | None] | None:
    """Returns `(approval, company_id)`, where `company_id` is set only when this decision
    approved the approval into a company (else None). Callers use `company_id` to trigger the
    M3 enrich stage after approve; None on an unknown/not-owned approval."""
    approval = await session.get(Approval, approval_id)
    if approval is None or approval.user_id != user_id:
        return None

    approval.decision = decision
    company: Company | None = None
    if decision == "approve":
        company = await _add_to_registry(session, user_id, approval)

    await session.flush()
    return approval, (company.id if company is not None else None)


async def _add_to_registry(session: AsyncSession, user_id: UUID, approval: Approval) -> Company:
    """Copy the approval's known fields into a company, respecting unique(user_id, domain).

    Enrichment (HQ confidence, comp estimate, real crawl) happens afterwards, out-of-band, via
    the M3 enrich stage — only the approval's already-known name/domain/logo/ats/hq_country are
    carried over here. Returns the existing or newly created company.
    """
    if approval.domain is not None:
        existing = await session.scalar(
            select(Company).where(Company.user_id == user_id, Company.domain == approval.domain)
        )
        if existing is not None:
            return existing

    company = Company(
        user_id=user_id,
        name=approval.name or approval.domain or "Unknown",
        domain=approval.domain,
        careers_url=approval.careers_url,
        logo_url=approval.logo_url,
        ats=approval.ats,
        hq_country=approval.hq_country,
    )
    session.add(company)
    return company
