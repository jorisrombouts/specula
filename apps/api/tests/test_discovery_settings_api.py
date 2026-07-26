import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from test_db import requires_db

from specula_api.auth import mint
from specula_api.config import settings
from specula_api.main import create_app


@pytest.fixture(autouse=True)
def _service_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "service_jwt_secret", "test-secret-at-least-32-bytes-long")


def _auth_header() -> dict[str, str]:
    sub, email = f"test-sub-{uuid.uuid4()}", f"{uuid.uuid4()}@example.com"
    return {"Authorization": f"Bearer {mint(sub=sub, email=email, name='T')}"}


@requires_db
async def test_get_returns_global_default_then_put_persists(migrated_db: None) -> None:
    headers = _auth_header()
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        got = await client.get("/api/v1/settings/discovery", headers=headers)
        assert got.status_code == 200
        assert got.json()["maxSearches"] == settings.discovery_max_searches  # global default (10)

        put = await client.put(
            "/api/v1/settings/discovery", json={"maxSearches": 7}, headers=headers
        )
        assert put.status_code == 200
        assert put.json()["maxSearches"] == 7

        again = await client.get("/api/v1/settings/discovery", headers=headers)
        assert again.json()["maxSearches"] == 7


@requires_db
async def test_put_rejects_out_of_range(migrated_db: None) -> None:
    headers = _auth_header()
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (
            await client.put("/api/v1/settings/discovery", json={"maxSearches": 0}, headers=headers)
        ).status_code == 422
        assert (
            await client.put(
                "/api/v1/settings/discovery", json={"maxSearches": 99}, headers=headers
            )
        ).status_code == 422
