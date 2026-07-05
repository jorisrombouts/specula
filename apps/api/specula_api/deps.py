from collections.abc import AsyncGenerator
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.auth import decode_service_jwt
from specula_api.db.models import User
from specula_api.db.session import async_session


async def get_current_user_id(authorization: str = Header(...)) -> UUID:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    try:
        claims = decode_service_jwt(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.google_sub == claims.sub))
        if user is not None:
            return user.id

        new_user = User(google_sub=claims.sub, email=claims.email, name=claims.name)
        session.add(new_user)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await session.scalar(select(User).where(User.google_sub == claims.sub))
            if existing is None:
                raise
            return existing.id
        return new_user.id


async def get_session(
    user_id: UUID = Depends(get_current_user_id),
) -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(user_id))
        )
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
