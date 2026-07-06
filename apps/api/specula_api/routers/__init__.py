from fastapi import APIRouter

from specula_api.routers import targeting, tweaks

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(targeting.router)
api_router.include_router(tweaks.router)
