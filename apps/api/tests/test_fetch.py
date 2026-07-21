from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from conftest import make_user, set_tenant
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

from specula_api.config import Settings
from specula_api.db.models import Company, Posting, Targeting
from specula_api.pipeline.content_hash import content_hash
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.fetch import FetchResult, fetch_postings
from specula_api.pipeline.http import FetchedDoc
from specula_api.pipeline.openai_client import EnrichResult, ExtractionResult, Source
from specula_api.pipeline.source import RawPosting


class _StubAdapter:
    """Hand-built SourceAdapter: returns a fixed list of RawPostings, or raises."""

    ats = "stub"

    def __init__(self, raws: list[RawPosting] | None = None, *, raises: bool = False) -> None:
        self._raws = raws or []
        self._raises = raises

    async def list_postings(self, company: object, fetcher: object) -> list[RawPosting]:
        if self._raises:
            raise RuntimeError("adapter blew up")
        return self._raws


class _StubFetcher:
    """Never actually called — resolve_adapter is monkeypatched to skip real ATS routing."""

    async def get(self, url: str, *, accept: str = "text/html") -> FetchedDoc:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None


class _StubOpenAI:
    """Hand-built OpenAIClient — see tests/test_discovery.py for why. Unused by fetch_postings."""

    async def discover_sources(
        self, queries: Sequence[str], *, allowed_domains: Sequence[str] | None = None
    ) -> list[Source]:
        raise NotImplementedError

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


def _deps(now: datetime) -> PipelineDeps:
    return PipelineDeps(
        openai=_StubOpenAI(),
        fetcher=_StubFetcher(),
        settings=Settings(),
        now=lambda: now,
    )


def _raw(url: str, *, external_id: str, title: str) -> RawPosting:
    return RawPosting(
        source_url=url,
        external_id=external_id,
        title_hint=title,
        content_hash=content_hash(source_url=url, external_id=external_id, title_hint=title),
    )


RAW_A = _raw("https://boards.greenhouse.io/acme/jobs/1", external_id="1", title="Engineer")
RAW_B = _raw("https://boards.greenhouse.io/acme/jobs/2", external_id="2", title="Designer")


@pytest.fixture(autouse=True)
def stub_resolve_adapter(monkeypatch: pytest.MonkeyPatch) -> list[_StubAdapter]:
    """Route fetch_postings at a single stub adapter instance per test, swappable via `.raws`."""
    adapters: list[_StubAdapter] = [_StubAdapter([])]

    def fake_resolve_adapter(company: object) -> _StubAdapter:
        return adapters[0]

    monkeypatch.setattr("specula_api.pipeline.fetch.resolve_adapter", fake_resolve_adapter)
    return adapters


async def _make_company(session: AsyncSession, user_id: object) -> Company:
    company = Company(user_id=user_id, name="Acme", domain="acme.com", ats="greenhouse")
    session.add(company)
    await session.flush()
    return company


# --- fetch_postings -------------------------------------------------------------


@requires_db
async def test_fetch_postings_inserts_provenance_shells_only(
    db_session: AsyncSession, stub_resolve_adapter: list[_StubAdapter]
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = await _make_company(db_session, user.id)
    stub_resolve_adapter[0] = _StubAdapter([RAW_A, RAW_B])
    now = datetime(2026, 7, 5, tzinfo=UTC)

    result = await fetch_postings(db_session, user.id, company, _deps(now))

    assert result == FetchResult(found=2, new=2, closed=0, errors=0)

    postings = (await db_session.scalars(select(Posting).where(Posting.user_id == user.id))).all()
    assert len(postings) == 2
    by_url = {p.source_url: p for p in postings}
    acme_1 = by_url["https://boards.greenhouse.io/acme/jobs/1"]
    assert acme_1.company_id == company.id
    assert acme_1.source == "greenhouse"
    assert acme_1.content_hash == RAW_A.content_hash
    assert acme_1.still_open is True
    assert acme_1.first_seen_at == now
    assert acme_1.last_seen_at == now
    # extraction/insight fields untouched — extract stage's job, not fetch's:
    assert acme_1.title is None
    assert acme_1.extraction_confidence is None
    assert acme_1.required_skills == []
    assert acme_1.title_vec is None
    assert acme_1.dedup_group is None


@requires_db
async def test_fetch_postings_is_idempotent_on_rerun(
    db_session: AsyncSession, stub_resolve_adapter: list[_StubAdapter]
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = await _make_company(db_session, user.id)
    stub_resolve_adapter[0] = _StubAdapter([RAW_A])
    first_now = datetime(2026, 7, 5, tzinfo=UTC)
    second_now = datetime(2026, 7, 6, tzinfo=UTC)

    first = await fetch_postings(db_session, user.id, company, _deps(first_now))
    second = await fetch_postings(db_session, user.id, company, _deps(second_now))

    assert first.new == 1
    assert second.found == 1
    assert second.new == 0
    assert second.closed == 0

    postings = (await db_session.scalars(select(Posting).where(Posting.user_id == user.id))).all()
    assert len(postings) == 1  # unique(user_id, content_hash) holds — no duplicate
    assert postings[0].last_seen_at == second_now
    assert postings[0].still_open is True


@requires_db
async def test_fetch_postings_closes_postings_missing_from_rerun(
    db_session: AsyncSession, stub_resolve_adapter: list[_StubAdapter]
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = await _make_company(db_session, user.id)
    stub_resolve_adapter[0] = _StubAdapter([RAW_A, RAW_B])
    first_now = datetime(2026, 7, 5, tzinfo=UTC)
    await fetch_postings(db_session, user.id, company, _deps(first_now))

    stub_resolve_adapter[0] = _StubAdapter([RAW_A])  # RAW_B no longer listed
    second_now = datetime(2026, 7, 6, tzinfo=UTC)
    second = await fetch_postings(db_session, user.id, company, _deps(second_now))

    assert second.closed == 1

    postings = {
        p.content_hash: p
        for p in (await db_session.scalars(select(Posting).where(Posting.user_id == user.id))).all()
    }
    assert postings[RAW_A.content_hash].still_open is True
    assert postings[RAW_B.content_hash].still_open is False


@requires_db
async def test_fetch_postings_does_not_mass_close_when_adapter_raises(
    db_session: AsyncSession, stub_resolve_adapter: list[_StubAdapter]
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = await _make_company(db_session, user.id)
    stub_resolve_adapter[0] = _StubAdapter([RAW_A, RAW_B])
    first_now = datetime(2026, 7, 5, tzinfo=UTC)
    await fetch_postings(db_session, user.id, company, _deps(first_now))

    stub_resolve_adapter[0] = _StubAdapter(raises=True)
    second_now = datetime(2026, 7, 6, tzinfo=UTC)
    second = await fetch_postings(db_session, user.id, company, _deps(second_now))

    assert second == FetchResult(found=0, new=0, closed=0, errors=1)

    postings = (await db_session.scalars(select(Posting).where(Posting.user_id == user.id))).all()
    assert all(p.still_open is True for p in postings)  # nothing mass-closed by the errored fetch


@requires_db
async def test_fetch_postings_is_tenant_scoped(
    db_session: AsyncSession, stub_resolve_adapter: list[_StubAdapter]
) -> None:
    owner = await make_user(db_session)
    other = await make_user(db_session)
    await set_tenant(db_session, owner.id)
    company = await _make_company(db_session, owner.id)
    stub_resolve_adapter[0] = _StubAdapter([RAW_A])
    now = datetime(2026, 7, 5, tzinfo=UTC)

    await fetch_postings(db_session, owner.id, company, _deps(now))

    await set_tenant(db_session, other.id)
    rows = (await db_session.scalars(select(Posting))).all()
    assert rows == []

    await set_tenant(db_session, owner.id)
    assert len((await db_session.scalars(select(Posting))).all()) == 1


@requires_db
async def test_fetch_postings_drops_raws_whose_title_does_not_match_target_role_titles(
    db_session: AsyncSession, stub_resolve_adapter: list[_StubAdapter]
) -> None:
    """The relevance gate (title_matches_roles) runs before shells are written: a big board is
    narrowed to the user's target roles, so an irrelevant feed title never becomes a Posting
    row at all (not just excluded downstream)."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = await _make_company(db_session, user.id)
    db_session.add(Targeting(user_id=user.id, role_titles=["Engineer"]))
    await db_session.flush()
    # RAW_A's title "Engineer" matches; RAW_B's title "Designer" does not.
    stub_resolve_adapter[0] = _StubAdapter([RAW_A, RAW_B])
    now = datetime(2026, 7, 5, tzinfo=UTC)

    result = await fetch_postings(db_session, user.id, company, _deps(now))

    assert result == FetchResult(found=1, new=1, closed=0, errors=0)
    postings = (await db_session.scalars(select(Posting).where(Posting.user_id == user.id))).all()
    assert len(postings) == 1
    assert postings[0].source_url == RAW_A.source_url


@requires_db
async def test_fetch_postings_does_not_close_still_listed_postings_when_targeting_narrows(
    db_session: AsyncSession, stub_resolve_adapter: list[_StubAdapter]
) -> None:
    """The relevance gate decides what gets EXTRACTED, not what counts as still on the board.

    `seen_hashes` must come from the UNFILTERED board listing: narrowing role_titles retires
    postings the board still advertises otherwise, reporting them as closed openings.
    """
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = await _make_company(db_session, user.id)
    db_session.add(Targeting(user_id=user.id, role_titles=["Engineer", "Designer"]))
    await db_session.flush()
    stub_resolve_adapter[0] = _StubAdapter([RAW_A, RAW_B])
    await fetch_postings(db_session, user.id, company, _deps(datetime(2026, 7, 5, tzinfo=UTC)))

    # The user narrows their targeting. The board still lists BOTH roles.
    targeting = await db_session.get(Targeting, user.id)
    assert targeting is not None
    targeting.role_titles = ["Engineer"]
    await db_session.flush()

    result = await fetch_postings(
        db_session, user.id, company, _deps(datetime(2026, 7, 6, tzinfo=UTC))
    )

    assert result.closed == 0
    postings = (await db_session.scalars(select(Posting).where(Posting.user_id == user.id))).all()
    assert [p.still_open for p in postings] == [True, True]


@requires_db
async def test_fetch_postings_keeps_all_raws_without_targeting(
    db_session: AsyncSession, stub_resolve_adapter: list[_StubAdapter]
) -> None:
    """No Targeting row at all (never onboarded) → nothing to filter against, so every raw
    posting is still written as a shell."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = await _make_company(db_session, user.id)
    stub_resolve_adapter[0] = _StubAdapter([RAW_A, RAW_B])
    now = datetime(2026, 7, 5, tzinfo=UTC)

    result = await fetch_postings(db_session, user.id, company, _deps(now))

    assert result == FetchResult(found=2, new=2, closed=0, errors=0)
