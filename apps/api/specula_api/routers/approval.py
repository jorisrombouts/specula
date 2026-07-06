from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.deps import get_current_user_id, get_session
from specula_api.schemas.approval import ApprovalOut, DecisionIn
from specula_api.services.approval import apply_decision, get_undecided_approvals

router = APIRouter(prefix="/approvals", tags=["approvals"])


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
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ApprovalOut:
    approval = await apply_decision(session, user_id, approval_id, data.decision)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return ApprovalOut.from_model(approval)
