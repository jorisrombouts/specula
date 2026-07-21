from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import make_user, set_tenant
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

from specula_api.config import Settings
from specula_api.db.models import Lens, Targeting
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.http import RecordedFetcher
from specula_api.pipeline.openai_client import EnrichResult, ExtractionResult, Source
from specula_api.services.run import create_run, run_discovery

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pipeline"


class _StubOpenAI:
    """Hand-built OpenAIClient stub — see tests/test_discovery.py for why."""

    def __init__(self, sources_by_query: dict[str, list[Source]]) -> None:
        self._sources_by_query = sources_by_query

    async def discover_sources(
        self, queries: Sequence[str], *, allowed_domains: Sequence[str] | None = None
    ) -> list[Source]:
        results: list[Source] = []
        for query in queries:
            results.extend(self._sources_by_query.get(query, []))
        return results

    async def enrich_company(
        self, *, name: str, domain: str | None, page_text: str | None
    ) -> EnrichResult:
        raise NotImplementedError

    async def extract_posting(
        self, *, page_text: str, company_name: str | None = None
    ) -> ExtractionResult:
        raise NotImplementedError

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError

    async def rationale(
        self, *, factors: dict[str, int], overlap: tuple[int, int], red_flag: str | None
    ) -> str:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None


def _deps(openai: _StubOpenAI) -> PipelineDeps:
    return PipelineDeps(
        openai=openai,
        fetcher=RecordedFetcher(FIXTURES_DIR),
        settings=Settings(),
        now=lambda: datetime(2026, 7, 5, tzinfo=UTC),
    )


@requires_db
async def test_run_discovery_transitions_queued_to_done_and_persists_stats(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    db_session.add(Targeting(user_id=user.id, role_titles=["ML Engineer"]))
    db_session.add(
        Lens(user_id=user.id, name="Fintech", seeds=["fintech"], scope="Remote EU", active=True)
    )
    await db_session.flush()
    run = await create_run(db_session, user.id)
    assert run.status == "queued"

    deps = _deps(
        _StubOpenAI(
            {
                "ML Engineer jobs Remote EU": [
                    Source(url="https://boards.greenhouse.io/acme/jobs/123", title="Acme role")
                ]
            }
        )
    )

    await run_discovery(db_session, user.id, run.id, deps)

    assert run.status == "done"
    assert run.started_at is not None
    assert run.finished_at is not None
    assert run.stats == {
        "found": 1,
        "new": 1,
        "closed": 0,
        "low_conf_excluded": 0,
        "errors": 0,
    }


@requires_db
async def test_run_discovery_error_path_sets_status_error_and_reraises(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    run = await create_run(db_session, user.id)
    deps = _deps(_StubOpenAI({}))

    async def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("specula_api.services.run.discover", _boom)

    with pytest.raises(RuntimeError):
        await run_discovery(db_session, user.id, run.id, deps)

    assert run.status == "error"
    assert run.stats["errors"] == 1
