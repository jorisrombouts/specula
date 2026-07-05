from fastapi import FastAPI

from specula_api.routers import api_router


def create_app() -> FastAPI:
    app = FastAPI(title="Specula API")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)

    return app


app = create_app()
