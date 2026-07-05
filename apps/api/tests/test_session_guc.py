import uuid

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

from specula_api.deps import get_current_user_id, get_session

app = FastAPI()


@app.get("/whoami")
async def whoami(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    result = await session.execute(text("SELECT current_setting('app.user_id')"))
    return {"user_id": result.scalar_one()}


@requires_db
async def test_get_session_sets_tenant_guc(migrated_db: None) -> None:
    user_id = uuid.uuid4()
    app.dependency_overrides[get_current_user_id] = lambda: user_id

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/whoami")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["user_id"] == str(user_id)


@requires_db
async def test_get_session_does_not_leak_between_requests(migrated_db: None) -> None:
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        app.dependency_overrides[get_current_user_id] = lambda: user_a
        response_a = await client.get("/whoami")

        app.dependency_overrides[get_current_user_id] = lambda: user_b
        response_b = await client.get("/whoami")

    app.dependency_overrides.clear()

    assert response_a.json()["user_id"] == str(user_a)
    assert response_b.json()["user_id"] == str(user_b)
