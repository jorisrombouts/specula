from fastapi import APIRouter

router = APIRouter(prefix="/account", tags=["account"])


@router.get("")
async def account_root() -> dict[str, str]:
    """Stub filled by the DATA lane."""
    return {"status": "not_implemented"}
