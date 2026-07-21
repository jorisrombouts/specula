from collections.abc import Sequence
from datetime import UTC, date, datetime

from conftest import make_user, set_tenant
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

from specula_api.config import Settings
from specula_api.db.models import Company, Posting
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.extract import extract_posting
from specula_api.pipeline.http import FetchedDoc
from specula_api.pipeline.openai_client import EnrichResult, ExtractionResult, Source
from specula_api.pipeline.util import html_to_text

_PAGE_TEXT = "Senior Backend Engineer — Acme Corp\n\nWe're hiring...\n"
_URL = "https://boards.greenhouse.io/acme/jobs/1"
_UNFETCHABLE_URL = "https://boards.greenhouse.io/acme/jobs/gone"

FULL_RESULT = ExtractionResult(
    title="Senior Backend Engineer",
    role_family="Backend Engineering",
    city="Berlin",
    country="DE",
    hq_country="US",
    work_mode="hybrid",
    seniority="senior",
    education=None,
    required_skills=["Python", "PostgreSQL"],
    nice_to_have=["Kubernetes"],
    visa="sponsorship available",
    languages=["English"],
    contract="full-time",
    geo="EU",
    salary_text="$140k-$190k",
    deadline_at=date(2026, 8, 15),
    posted_at=date(2026, 6, 1),
    responsibilities=["Design distributed systems"],
    summary="Senior backend role at Acme Corp.",
    extraction_confidence=82,
)


class _StubFetcher:
    """Returns a fixed FetchedDoc per URL; unknown URLs 404 (models an unfetchable page)."""

    def __init__(self, docs: dict[str, FetchedDoc]) -> None:
        self._docs = docs
        self.calls: list[str] = []

    async def get(self, url: str, *, accept: str = "text/html") -> FetchedDoc:
        self.calls.append(url)
        return self._docs.get(url, FetchedDoc(url=url, status=404, text=""))

    async def aclose(self) -> None:
        return None


class _StubOpenAI:
    """Hand-built OpenAIClient stub — see tests/test_discovery.py for why."""

    def __init__(self, result: ExtractionResult) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

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
        self.calls.append({"page_text": page_text, "company_name": company_name})
        return self._result

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError

    async def rationale(
        self, *, factors: dict[str, int], overlap: tuple[int, int], red_flag: str | None
    ) -> str:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None


def _deps(openai: _StubOpenAI, fetcher: _StubFetcher) -> PipelineDeps:
    return PipelineDeps(
        openai=openai,
        fetcher=fetcher,
        settings=Settings(),
        now=lambda: datetime(2026, 7, 5, tzinfo=UTC),
    )


async def _make_posting_shell(
    session: AsyncSession, user_id: object, company: Company | None, source_url: str
) -> Posting:
    posting = Posting(
        user_id=user_id,
        company_id=company.id if company else None,
        source="greenhouse",
        source_url=source_url,
        content_hash=f"hash-{source_url}",
    )
    session.add(posting)
    await session.flush()
    return posting


# --- extract_posting ------------------------------------------------------------


@requires_db
async def test_extract_posting_applies_all_fields_from_result(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = Company(user_id=user.id, name="Acme", domain="acme.com")
    db_session.add(company)
    await db_session.flush()
    posting = await _make_posting_shell(db_session, user.id, company, _URL)

    fetcher = _StubFetcher({_URL: FetchedDoc(url=_URL, status=200, text=_PAGE_TEXT)})
    openai = _StubOpenAI(FULL_RESULT)

    await extract_posting(db_session, posting, _deps(openai, fetcher))

    assert posting.title == "Senior Backend Engineer"
    assert posting.role_family == "Backend Engineering"
    assert posting.city == "Berlin"
    assert posting.country == "DE"
    assert posting.hq_country == "US"
    assert posting.work_mode == "hybrid"
    assert posting.seniority == "senior"
    assert posting.education is None
    assert posting.required_skills == ["Python", "PostgreSQL"]
    assert posting.nice_to_have == ["Kubernetes"]
    assert posting.visa == "sponsorship available"
    assert posting.languages == ["English"]
    assert posting.contract == "full-time"
    assert posting.geo == "EU"
    assert posting.salary_text == "$140k-$190k"
    assert posting.deadline_at == date(2026, 8, 15)
    assert posting.posted_at == date(2026, 6, 1)
    assert posting.responsibilities == ["Design distributed systems"]
    assert posting.summary == "Senior backend role at Acme Corp."
    assert posting.extraction_confidence == 82
    # provenance/lifecycle fields untouched:
    assert posting.source == "greenhouse"
    assert posting.still_open is True
    assert fetcher.calls == [_URL]
    # The fetched page is reduced via html_to_text() before it reaches the LLM — raw HTML
    # overflowed the 128k context on a real run (context_length_exceeded).
    assert openai.calls == [{"page_text": html_to_text(_PAGE_TEXT), "company_name": "Acme"}]


@requires_db
async def test_extract_posting_passes_none_company_name_when_no_company(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    posting = await _make_posting_shell(db_session, user.id, None, _URL)

    fetcher = _StubFetcher({_URL: FetchedDoc(url=_URL, status=200, text=_PAGE_TEXT)})
    openai = _StubOpenAI(FULL_RESULT)

    await extract_posting(db_session, posting, _deps(openai, fetcher))

    assert openai.calls == [{"page_text": html_to_text(_PAGE_TEXT), "company_name": None}]


@requires_db
async def test_extract_posting_never_invents_salary(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    posting = await _make_posting_shell(db_session, user.id, None, _URL)

    fetcher = _StubFetcher({_URL: FetchedDoc(url=_URL, status=200, text=_PAGE_TEXT)})
    result = FULL_RESULT.model_copy(update={"salary_text": None})
    openai = _StubOpenAI(result)

    await extract_posting(db_session, posting, _deps(openai, fetcher))

    assert posting.salary_text is None


@requires_db
async def test_extract_posting_stores_low_confidence_result_without_dropping(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    posting = await _make_posting_shell(db_session, user.id, None, _URL)

    fetcher = _StubFetcher({_URL: FetchedDoc(url=_URL, status=200, text=_PAGE_TEXT)})
    result = FULL_RESULT.model_copy(update={"extraction_confidence": 30})
    openai = _StubOpenAI(result)

    await extract_posting(db_session, posting, _deps(openai, fetcher))

    assert posting.title == "Senior Backend Engineer"  # not dropped
    assert posting.extraction_confidence == 30  # below low_confidence_threshold (50)


@requires_db
async def test_extract_posting_unfetchable_page_gets_zero_confidence_and_placeholder_title(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    posting = await _make_posting_shell(db_session, user.id, None, _UNFETCHABLE_URL)

    fetcher = _StubFetcher({})  # every URL 404s
    openai = _StubOpenAI(FULL_RESULT)

    await extract_posting(db_session, posting, _deps(openai, fetcher))

    assert posting.extraction_confidence == 0
    assert posting.title is not None  # placeholder set — no longer `title IS NULL`
    assert openai.calls == []  # never called the LLM on an unfetchable page

    # the "needs extraction" filter (`title IS NULL`) no longer selects this posting:
    remaining = (
        await db_session.scalars(
            select(Posting).where(Posting.user_id == user.id, Posting.title.is_(None))
        )
    ).all()
    assert remaining == []


@requires_db
async def test_extract_posting_empty_page_text_gets_zero_confidence(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    posting = await _make_posting_shell(db_session, user.id, None, _URL)

    fetcher = _StubFetcher({_URL: FetchedDoc(url=_URL, status=200, text="")})
    openai = _StubOpenAI(FULL_RESULT)

    await extract_posting(db_session, posting, _deps(openai, fetcher))

    assert posting.extraction_confidence == 0
    assert posting.title is not None
    assert openai.calls == []
