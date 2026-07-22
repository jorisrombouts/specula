from specula_api.main import create_app


def test_dashboard_and_account_routers_registered() -> None:
    # `app.routes` on this FastAPI/Starlette version yields opaque `_IncludedRouter`
    # wrappers (no `.path`) for included routers; the OpenAPI schema is the stable,
    # version-independent way to assert which paths are registered.
    paths = set(create_app().openapi()["paths"])
    assert "/api/v1/dashboard" in paths
    assert "/api/v1/account" in paths
