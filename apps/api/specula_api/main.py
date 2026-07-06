from fastapi import FastAPI

from specula_api.config import settings
from specula_api.routers import api_router


def create_app() -> FastAPI:
    # Fail fast on a misconfigured service-JWT secret: an empty HMAC key would let
    # any token signed with "" validate (forged `sub` → full auth bypass). Allowed
    # only in development, where DB tests set it per-run.
    if not settings.service_jwt_secret and settings.app_env != "development":
        raise RuntimeError("SERVICE_JWT_SECRET must be set (empty secret accepts forged tokens).")

    app = FastAPI(title="Specula API")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)

    return app


app = create_app()
