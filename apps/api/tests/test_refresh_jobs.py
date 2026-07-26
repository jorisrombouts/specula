from typing import cast
from uuid import UUID, uuid4

import pytest
from conftest import make_user, set_tenant
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

import specula_api.services.run as run_service
from specula_api.db.models import Company, Posting
from specula_api.pipeline.deps import PipelineDeps
from specula_api.services.run import refresh_all_jobs


@requires_db
async def test_refresh_all_jobs_ingests_tracked_and_skips_opted_out(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """refresh_all_jobs loops the per-company ingest over every tracked company, skips opted-out
    ones, and returns the count of NEW postings found across the loop."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    kept1 = Company(user_id=user.id, name="A", domain="a.example")
    kept2 = Company(user_id=user.id, name="B", domain="b.example")
    removed = Company(user_id=user.id, name="C", domain="c.example", opt_out=True)
    db_session.add_all([kept1, kept2, removed])
    await db_session.flush()
    kept_ids = {kept1.id, kept2.id}

    ingested: list[UUID] = []

    async def _spy(session: AsyncSession, user_id: UUID, company_id: UUID, deps: object) -> None:
        ingested.append(company_id)
        session.add(
            Posting(
                user_id=user_id,
                company_id=company_id,
                source="scrape",
                source_url=f"https://x/{uuid4()}",
                content_hash=f"h-{uuid4()}",
            )
        )
        await session.flush()

    monkeypatch.setattr(run_service, "ingest_company", _spy)

    new = await refresh_all_jobs(db_session, user.id, cast(PipelineDeps, None))

    assert set(ingested) == kept_ids  # opted-out company never crawled
    assert new == 2  # one new posting per tracked company
