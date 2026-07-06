from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

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
