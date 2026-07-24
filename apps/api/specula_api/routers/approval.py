from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.deps import get_current_user_id, get_session
from specula_api.ratelimit import RateLimitedRoute, enforce_ingest_rate_limit
from specula_api.schemas.approval import ApprovalOut, DecisionIn
from specula_api.services.approval import apply_decision, get_undecided_approvals
from specula_api.services.run import trigger_company_ingest

router = APIRouter(prefix="/approvals", tags=["approvals"], route_class=RateLimitedRoute)


@router.get("")
async def list_approvals(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[ApprovalOut]:
    approvals = await get_undecided_approvals(session, user_id)
    return [ApprovalOut.from_model(a) for a in approvals]


@router.post("/{approval_id}/decision")
async def decide_approval(
    approval_id: UUID,
    data: DecisionIn,
    background_tasks: BackgroundTasks,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ApprovalOut:
    result = await apply_decision(session, user_id, approval_id, data.decision)
    if result is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    approval, company_id = result
    if company_id is not None:
        # Gate exactly the approve->ingest trigger (a heavy crawl+LLM pass), not cheap
        # reject/snooze decisions — and via the ingest bucket (its own hourly cap, no cooldown)
        # so working through the queue isn't throttled by the discovery-run cooldown. Raising
        # here rolls back the decision via get_session, so a rate-limited approve stays undecided
        # and the retry re-applies it and ingests together.
        enforce_ingest_rate_limit(user_id)
        # get_session's post-yield commit doesn't run until after the response
        # (including BackgroundTasks) has been sent — FastAPI's dependency
        # AsyncExitStack now outlives the response to support streaming responses.
        # Commit explicitly so the company row is durably visible to the
        # background task's own tenant_session connection before it starts.
        await session.commit()
        background_tasks.add_task(trigger_company_ingest, user_id, company_id)
    return ApprovalOut.from_model(approval)
