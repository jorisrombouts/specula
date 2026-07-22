import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from test_db import requires_db

from specula_api.auth import mint
from specula_api.config import settings
from specula_api.db.models import Company, User
from specula_api.db.session import async_session, tenant_session
from specula_api.main import create_app


@pytest.fixture(autouse=True)
def _service_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "service_jwt_secret", "test-secret-at-least-32-bytes-long")


async def _make_user() -> User:
    async with async_session() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", google_sub=f"test-sub-{uuid.uuid4()}")
        session.add(user)
        await session.commit()
        return user


def _auth_header(user: User) -> dict[str, str]:
    token = mint(sub=user.google_sub, email=user.email, name="Test User")
    return {"Authorization": f"Bearer {token}"}


async def _make_company(user_id: uuid.UUID, *, domain: str) -> uuid.UUID:
    async with tenant_session(user_id) as session:
        company = Company(user_id=user_id, name="Acme", domain=domain)
        session.add(company)
        await session.flush()
        return company.id


async def _opt_out(user_id: uuid.UUID, company_id: uuid.UUID) -> bool | None:
    async with tenant_session(user_id) as session:
        company = await session.get(Company, company_id)
        return company.opt_out if company is not None else None


async def _cleanup_users(*user_ids: uuid.UUID) -> None:
    async with async_session() as session:
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@requires_db
async def test_opt_out_sets_flag(migrated_db: None) -> None:
    user = await _make_user()
    try:
        company_id = await _make_company(user.id, domain="acme-optout.example")
        assert await _opt_out(user.id, company_id) is False

        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/companies/{company_id}/opt-out", headers=_auth_header(user)
            )

        assert response.status_code == 204
        assert await _opt_out(user.id, company_id) is True
    finally:
        await _cleanup_users(user.id)


@requires_db
async def test_opt_out_unknown_company_returns_404(migrated_db: None) -> None:
    user = await _make_user()
    try:
        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/companies/{uuid.uuid4()}/opt-out", headers=_auth_header(user)
            )
        assert response.status_code == 404
    finally:
        await _cleanup_users(user.id)


@requires_db
async def test_opt_out_cannot_affect_another_tenant(migrated_db: None) -> None:
    user_a = await _make_user()
    user_b = await _make_user()
    try:
        company_id = await _make_company(user_a.id, domain="acme-cross.example")

        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/companies/{company_id}/opt-out", headers=_auth_header(user_b)
            )

        # B cannot see A's company — RLS hides it, so it reads as not-found.
        assert response.status_code == 404
        assert await _opt_out(user_a.id, company_id) is False
    finally:
        await _cleanup_users(user_a.id, user_b.id)
