from fastapi import APIRouter

from specula_api.routers import (
    account,
    approval,
    candidate,
    company,
    dashboard,
    insights,
    jobs,
    lenses,
    run,
    targeting,
    tweaks,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(account.router)
api_router.include_router(approval.router)
api_router.include_router(candidate.router)
api_router.include_router(company.router)
api_router.include_router(dashboard.router)
api_router.include_router(insights.router)
api_router.include_router(jobs.router)
api_router.include_router(lenses.router)
api_router.include_router(run.router)
api_router.include_router(targeting.router)
api_router.include_router(tweaks.router)
