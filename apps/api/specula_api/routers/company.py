from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import Company
from specula_api.deps import get_current_user_id, get_session
from specula_api.schemas.company import CompanyOut, CompanyPatch
from specula_api.services.company import DomainConflictError, list_companies, patch_company

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("")
async def read_companies(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[CompanyOut]:
    rows = await list_companies(session, user_id)
    return [CompanyOut.from_model(company, open_roles) for company, open_roles in rows]


@router.patch("/{company_id}")
async def update_company(
    company_id: UUID,
    data: CompanyPatch,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> CompanyOut:
    try:
        result = await patch_company(session, user_id, company_id, data)
    except DomainConflictError:
        raise HTTPException(
            status_code=409, detail="A company with that domain already exists"
        ) from None

    if result is None:
        raise HTTPException(status_code=404, detail="Company not found")

    company, open_roles = result
    return CompanyOut.from_model(company, open_roles)


@router.post("/{company_id}/opt-out", status_code=204)
async def opt_out_company(
    company_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Per-company removal (spec §15): flag the company so it's excluded from future ingest.
    RLS hides other tenants' rows, so a cross-tenant id reads as not-found; the explicit
    `user_id` check is the second guard."""
    company = await session.get(Company, company_id)
    if company is None or company.user_id != user_id:
        raise HTTPException(status_code=404, detail="Company not found")
    company.opt_out = True
    await session.flush()
    return Response(status_code=204)
