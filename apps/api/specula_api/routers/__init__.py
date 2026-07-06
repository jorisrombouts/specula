from fastapi import APIRouter

from specula_api.routers import company, targeting

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(company.router)
api_router.include_router(targeting.router)
