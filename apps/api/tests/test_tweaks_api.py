import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from test_db import requires_db

from specula_api.auth import mint
from specula_api.config import settings
from specula_api.main import create_app

DEFAULTS = {
    "mstyle": "bars",
    "layout": "rows",
    "density": "comfortable",
    "accent": "#2E7D4F",
    "font": "Spectral",
}


@pytest.fixture(autouse=True)
def _service_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "service_jwt_secret", "test-secret-at-least-32-bytes-long")


def _auth_header() -> dict[str, str]:
    sub = f"test-sub-{uuid.uuid4()}"
    email = f"{uuid.uuid4()}@example.com"
    token = mint(sub=sub, email=email, name="Test User")
    return {"Authorization": f"Bearer {token}"}


@requires_db
async def test_get_tweaks_for_fresh_user_returns_defaults(migrated_db: None) -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/tweaks", headers=_auth_header())

    assert response.status_code == 200
    assert response.json() == DEFAULTS


@requires_db
async def test_put_tweaks_persists_and_echoes(migrated_db: None) -> None:
    headers = _auth_header()
    payload = {
        "mstyle": "ring",
        "layout": "cards",
        "density": "compact",
        "accent": "#2D5BBF",
        "font": "Newsreader",
    }

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_response = await client.put("/api/v1/tweaks", json=payload, headers=headers)
        assert put_response.status_code == 200
        assert put_response.json() == payload

        get_response = await client.get("/api/v1/tweaks", headers=headers)
        assert get_response.status_code == 200
        assert get_response.json() == payload


@requires_db
async def test_put_tweaks_rejects_invalid_enum(migrated_db: None) -> None:
    headers = _auth_header()
    bad_payloads = [
        {**DEFAULTS, "mstyle": "sparkline"},
        {**DEFAULTS, "layout": "grid"},
        {**DEFAULTS, "density": "cozy"},
        {**DEFAULTS, "accent": "#FF0000"},
        {**DEFAULTS, "font": "Comic Sans"},
    ]

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for payload in bad_payloads:
            response = await client.put("/api/v1/tweaks", json=payload, headers=headers)
            assert response.status_code == 422, payload


@requires_db
async def test_cross_tenant_isolation(migrated_db: None) -> None:
    user_a_headers = _auth_header()
    user_b_headers = _auth_header()
    payload = {**DEFAULTS, "mstyle": "ring"}

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_response = await client.put("/api/v1/tweaks", json=payload, headers=user_a_headers)
        assert put_response.status_code == 200

        get_response = await client.get("/api/v1/tweaks", headers=user_b_headers)
        assert get_response.status_code == 200
        assert get_response.json() == DEFAULTS
