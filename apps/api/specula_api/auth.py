import time
from typing import Any

import jwt
from pydantic import BaseModel

from specula_api.config import settings


class ServiceClaims(BaseModel):
    sub: str
    email: str
    name: str | None = None


def decode_service_jwt(token: str) -> ServiceClaims:
    payload: dict[str, Any] = jwt.decode(
        token,
        settings.service_jwt_secret,
        algorithms=["HS256"],
        audience=settings.service_jwt_audience,
        issuer=settings.service_jwt_issuer,
        leeway=5,
        # Reject tokens missing these claims outright — a misconfigured minter must
        # not be able to produce a non-expiring or unaudienced token.
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
    )
    return ServiceClaims.model_validate(payload)


def mint(sub: str, email: str, name: str | None = None, ttl: int = 60) -> str:
    iat = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "name": name,
        "iss": settings.service_jwt_issuer,
        "aud": settings.service_jwt_audience,
        "iat": iat,
        "exp": iat + ttl,
    }
    return jwt.encode(payload, settings.service_jwt_secret, algorithm="HS256")
