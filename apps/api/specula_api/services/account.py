"""Account data-management services: GDPR export of the caller's own data, and account
deletion via FK cascade. Both run under a session whose `app.user_id` GUC is set (RLS binds),
and additionally scope every read by `user_id` — belt-and-suspenders alongside RLS. The global
`skills_taxonomy` table is unscoped and is excluded from both paths by construction."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import (
    CandidateProfile,
    Company,
    Lens,
    LlmCost,
    Posting,
    Run,
    Score,
    Targeting,
    User,
)
from specula_api.schemas.account import (
    CandidateExport,
    CompanyExport,
    ExportBundle,
    LensExport,
    LlmCostExport,
    PostingExport,
    RunExport,
    ScoreExport,
    TargetingExport,
)


async def export_account(session: AsyncSession, user_id: UUID) -> ExportBundle:
    """Gather every per-user table the frozen `ExportBundle` covers. RLS auto-scopes the
    reads; the explicit `user_id` filters are the belt-and-suspenders second guard."""
    candidate = await session.get(CandidateProfile, user_id)
    targeting = await session.get(Targeting, user_id)

    companies = (
        await session.scalars(
            select(Company).where(Company.user_id == user_id).order_by(Company.added_at)
        )
    ).all()
    postings = (
        await session.scalars(
            select(Posting).where(Posting.user_id == user_id).order_by(Posting.first_seen_at)
        )
    ).all()
    scores = (await session.scalars(select(Score).where(Score.user_id == user_id))).all()
    lenses = (
        await session.scalars(select(Lens).where(Lens.user_id == user_id).order_by(Lens.created_at))
    ).all()
    runs = (
        await session.scalars(select(Run).where(Run.user_id == user_id).order_by(Run.created_at))
    ).all()
    llm_costs = (
        await session.scalars(
            select(LlmCost).where(LlmCost.user_id == user_id).order_by(LlmCost.created_at)
        )
    ).all()

    return ExportBundle(
        exported_at=datetime.now(UTC),
        candidate=CandidateExport.model_validate(candidate) if candidate is not None else None,
        targeting=TargetingExport.model_validate(targeting) if targeting is not None else None,
        companies=[CompanyExport.model_validate(c) for c in companies],
        postings=[PostingExport.model_validate(p) for p in postings],
        scores=[ScoreExport.model_validate(s) for s in scores],
        lenses=[LensExport.model_validate(lens) for lens in lenses],
        runs=[RunExport.model_validate(r) for r in runs],
        llm_costs=[LlmCostExport.model_validate(c) for c in llm_costs],
    )


async def delete_account(session: AsyncSession, user_id: UUID) -> None:
    """Delete the caller's identity row. Every tenant table's `user_id` FK is
    `ON DELETE CASCADE`, so this removes all of the user's rows (incl. `llm_costs`); the
    global `skills_taxonomy` has no such FK and is untouched by construction."""
    await session.execute(delete(User).where(User.id == user_id))
    await session.flush()
