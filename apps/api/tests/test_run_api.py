import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from test_db import requires_db

from specula_api.auth import mint
from specula_api.config import settings
from specula_api.main import create_app

_ZERO_STATS = {"found": 0, "new": 0, "closed": 0, "lowConfExcluded": 0, "errors": 0, "scored": 0}


@pytest.fixture(autouse=True)
def _service_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "service_jwt_secret", "test-secret-at-least-32-bytes-long")


def _auth_header() -> dict[str, str]:
    sub = f"test-sub-{uuid.uuid4()}"
    email = f"{uuid.uuid4()}@example.com"
    token = mint(sub=sub, email=email, name="Test User")
    return {"Authorization": f"Bearer {token}"}


@requires_db
async def test_post_runs_creates_queued_run_that_completes_inline(migrated_db: None) -> None:
    headers = _auth_header()
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        post_response = await client.post("/api/v1/runs", headers=headers)
        assert post_response.status_code == 201
        body = post_response.json()
        assert body["status"] == "queued"
        assert body["kind"] == "on_demand"
        assert body["stats"] == _ZERO_STATS

        # Inline execution runs in a BackgroundTask, which ASGITransport executes
        # before the client call returns — the run has already reached its
        # terminal state by the time we follow up with a GET.
        latest_response = await client.get("/api/v1/runs/latest", headers=headers)
        assert latest_response.status_code == 200
        latest_body = latest_response.json()
        assert latest_body["id"] == body["id"]
        assert latest_body["status"] == "done"
        assert latest_body["stats"] == _ZERO_STATS


@requires_db
async def test_post_rescore_creates_a_rescore_run_that_completes_inline(migrated_db: None) -> None:
    headers = _auth_header()
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/runs/rescore", headers=headers)
        assert res.status_code == 201
        body = res.json()
        assert body["kind"] == "rescore"
        assert body["status"] == "queued"

        # The BackgroundTask ran inline; fetch the run by id (latest excludes rescore).
        got = await client.get(f"/api/v1/runs/{body['id']}", headers=headers)
        assert got.status_code == 200
        run = got.json()
        assert run["status"] == "done"
        assert run["stats"]["scored"] == 0  # fresh user, nothing to score

        # A rescore must NOT surface as the discovery "synced" run in the sidebar.
        latest = await client.get("/api/v1/runs/latest", headers=headers)
        assert latest.status_code == 200
        assert latest.json() is None


@requires_db
async def test_get_latest_run_returns_null_when_none_exist(migrated_db: None) -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/runs/latest", headers=_auth_header())
    assert response.status_code == 200
    assert response.json() is None


@requires_db
async def test_get_run_for_unknown_id_returns_404(migrated_db: None) -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/v1/runs/{uuid.uuid4()}", headers=_auth_header())
    assert response.status_code == 404


@requires_db
async def test_cross_tenant_get_run_returns_404(migrated_db: None) -> None:
    headers_a = _auth_header()
    headers_b = _auth_header()

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        post_response = await client.post("/api/v1/runs", headers=headers_a)
        run_id = post_response.json()["id"]

        response = await client.get(f"/api/v1/runs/{run_id}", headers=headers_b)
    assert response.status_code == 404
