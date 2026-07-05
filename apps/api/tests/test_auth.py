import time
import uuid

import jwt
import pytest
from sqlalchemy import select
from test_db import requires_db

from specula_api.auth import ServiceClaims, decode_service_jwt, mint
from specula_api.config import settings
from specula_api.db.models import User
from specula_api.db.session import async_session
from specula_api.deps import get_current_user_id


@pytest.fixture(autouse=True)
def _service_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "service_jwt_secret", "test-secret-at-least-32-bytes-long")


def test_mint_decodes_to_expected_claims() -> None:
    token = mint(sub="google-sub-123", email="user@example.com", name="Test User")

    claims = decode_service_jwt(token)

    assert claims == ServiceClaims(sub="google-sub-123", email="user@example.com", name="Test User")


def test_mint_without_name_defaults_to_none() -> None:
    token = mint(sub="google-sub-123", email="user@example.com")

    claims = decode_service_jwt(token)

    assert claims.name is None


def test_expired_token_raises() -> None:
    token = mint(sub="google-sub-123", email="user@example.com", ttl=-10)

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_service_jwt(token)


def test_wrong_audience_raises() -> None:
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "google-sub-123",
            "email": "user@example.com",
            "iss": settings.service_jwt_issuer,
            "aud": "someone-else",
            "iat": now,
            "exp": now + 60,
        },
        settings.service_jwt_secret,
        algorithm="HS256",
    )

    with pytest.raises(jwt.InvalidAudienceError):
        decode_service_jwt(token)


def test_token_missing_required_claim_raises() -> None:
    # A token missing exp/iat/iss is rejected outright by the require-options guard.
    token = jwt.encode(
        {"sub": "s", "email": "u@example.com", "aud": settings.service_jwt_audience},
        settings.service_jwt_secret,
        algorithm="HS256",
    )

    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_service_jwt(token)


@requires_db
async def test_get_current_user_id_finds_or_creates_idempotently(migrated_db: None) -> None:
    sub = f"test-sub-{uuid.uuid4()}"
    email = f"{uuid.uuid4()}@example.com"
    token = mint(sub=sub, email=email, name="Idempotent User")

    first_id = await get_current_user_id(authorization=f"Bearer {token}")
    second_id = await get_current_user_id(authorization=f"Bearer {token}")

    assert first_id == second_id

    async with async_session() as session:
        rows = (await session.scalars(select(User).where(User.google_sub == sub))).all()
        assert len(rows) == 1
        assert rows[0].id == first_id
