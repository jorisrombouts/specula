from fastapi import APIRouter

from specula_api.routers import candidate, lenses, targeting

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(candidate.router)
api_router.include_router(targeting.router)
api_router.include_router(lenses.router)
