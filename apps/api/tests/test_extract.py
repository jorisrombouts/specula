from collections.abc import Sequence
from datetime import UTC, date, datetime

from conftest import make_user, set_tenant
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

from specula_api.config import Settings
from specula_api.db.models import Company, Lens, Posting
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.extract import extract_posting
from specula_api.pipeline.http import FetchedDoc
from specula_api.pipeline.openai_client import EnrichResult, ExtractionResult, Source
from specula_api.pipeline.util import html_to_text
from specula_api.services.lens_filter import lens_where

# A realistic posting page: extraction now requires meaningfully readable text, so a
# two-word stub would (correctly) be treated as an unextractable shell.
_PAGE_TEXT = (
    "Senior Backend Engineer at Acme Corp. We are hiring a senior backend engineer to "
    "join our platform team in Berlin. You will design and operate distributed services, "
    "own critical APIs end to end, and partner closely with product and data. "
    "Requirements: five or more years building production backends, strong Python and "
    "SQL, experience with asynchronous services and cloud infrastructure. Nice to have: "
    "Kubernetes and event-driven architectures."
)
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

    async def approval_whys(self, descriptions: Sequence[str]) -> list[str]:
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


@requires_db
async def test_extract_posting_skips_js_rendered_shell_with_no_readable_text(
    db_session: AsyncSession,
) -> None:
    """A JS-rendered board (e.g. Ashby) answers 200 with kilobytes of SPA markup that
    reduces to zero readable text. That is not extractable content: it must be flagged like
    an unfetchable page rather than sent to the model, which previously hallucinated a
    posting titled after the response schema itself."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    posting = await _make_posting_shell(db_session, user.id, None, _URL)

    shell = (
        "<!doctype html><html><head><title>x</title>"
        '<script>window.__DATA__={"a":1};</script><style>.x{color:red}</style></head>'
        '<body><div id="root"></div><script src="/bundle.js"></script></body></html>'
    )
    fetcher = _StubFetcher({_URL: FetchedDoc(url=_URL, status=200, text=shell)})
    openai = _StubOpenAI(FULL_RESULT)

    await extract_posting(db_session, posting, _deps(openai, fetcher))

    assert posting.extraction_confidence == 0
    assert posting.title is not None
    assert "extractable" in posting.title
    assert openai.calls == []  # never billed for a page with nothing to read


# --- country normalization -------------------------------------------------------


@requires_db
async def test_extract_posting_normalizes_full_country_name_to_alpha2(
    db_session: AsyncSession,
) -> None:
    """The LLM sometimes emits a full country name rather than the alpha-2 code every
    consumer (lens_filter, the flag emoji, foreign-HQ comparisons) expects. `extract_posting`
    must normalize on write so the stored value is always canonical."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    posting = await _make_posting_shell(db_session, user.id, None, _URL)

    fetcher = _StubFetcher({_URL: FetchedDoc(url=_URL, status=200, text=_PAGE_TEXT)})
    result = FULL_RESULT.model_copy(update={"country": "Spain", "hq_country": "United Kingdom"})
    openai = _StubOpenAI(result)

    await extract_posting(db_session, posting, _deps(openai, fetcher))

    assert posting.country == "ES"
    assert posting.hq_country == "GB"


@requires_db
async def test_extract_posting_keeps_a_correct_alpha2_code(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    posting = await _make_posting_shell(db_session, user.id, None, _URL)

    fetcher = _StubFetcher({_URL: FetchedDoc(url=_URL, status=200, text=_PAGE_TEXT)})
    openai = _StubOpenAI(FULL_RESULT)  # country="DE", hq_country="US" — already alpha-2

    await extract_posting(db_session, posting, _deps(openai, fetcher))

    assert posting.country == "DE"
    assert posting.hq_country == "US"


@requires_db
async def test_extract_posting_with_full_country_name_now_matches_its_lens(
    db_session: AsyncSession,
) -> None:
    """Regression test for the bug this normalization fixes: a posting extracted with
    country="Spain" used to be invisible to a lens scoped to `scope="ES"`, because
    `lens_filter._scope_predicate` does a literal `Posting.country == "ES"` — comparing a
    country code against a full name never matched, so every location-scoped lens silently
    dropped all real crawled postings. With normalization on write, the same posting is now
    returned."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    posting = await _make_posting_shell(db_session, user.id, None, _URL)

    fetcher = _StubFetcher({_URL: FetchedDoc(url=_URL, status=200, text=_PAGE_TEXT)})
    result = FULL_RESULT.model_copy(update={"country": "Spain"})
    openai = _StubOpenAI(result)

    await extract_posting(db_session, posting, _deps(openai, fetcher))

    spain_lens = Lens(user_id=user.id, name="Spain", scope="ES", is_default=False)
    matched = (
        await db_session.scalars(
            select(Posting).where(Posting.id == posting.id, *lens_where(spain_lens))
        )
    ).all()

    assert matched == [posting]
