from fastapi import APIRouter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def dashboard_root() -> dict[str, str]:
    """Stub filled by the DASH lane."""
    return {"status": "not_implemented"}
