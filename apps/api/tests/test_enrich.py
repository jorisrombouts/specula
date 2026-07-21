from collections.abc import Sequence
from datetime import UTC, datetime

from conftest import make_user, set_tenant
from sqlalchemy.ext.asyncio import AsyncSession
from test_db import requires_db

from specula_api.config import Settings
from specula_api.db.models import Company, Posting
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.enrich import enrich_company
from specula_api.pipeline.http import FetchedDoc
from specula_api.pipeline.openai_client import EnrichResult, ExtractionResult, Source
from specula_api.services.run import ingest_company

# A realistic posting page: extraction now requires meaningfully readable text, so a
# two-word stub would (correctly) be treated as an unextractable shell.
_JOB_PAGE_TEXT = (
    "Senior Backend Engineer at Acme Corp. We are hiring a senior backend engineer to "
    "join our platform team in Berlin. You will design and operate distributed services, "
    "own critical APIs end to end, and partner closely with product and data. "
    "Requirements: five or more years building production backends, strong Python and "
    "SQL, experience with asynchronous services and cloud infrastructure. Nice to have: "
    "Kubernetes and event-driven architectures."
)


class _StubFetcher:
    """Returns a fixed doc for every URL requested; records the URLs it was called with."""

    def __init__(self, doc: FetchedDoc) -> None:
        self._doc = doc
        self.calls: list[str] = []

    async def get(self, url: str, *, accept: str = "text/html") -> FetchedDoc:
        self.calls.append(url)
        return self._doc

    async def aclose(self) -> None:
        return None


class _StubOpenAI:
    """Hand-built OpenAIClient stub — see tests/test_discovery.py for why."""

    def __init__(
        self, result: EnrichResult, *, extract_result: ExtractionResult | None = None
    ) -> None:
        self._result = result
        self._extract_result = extract_result
        self.calls: list[dict[str, object]] = []

    async def discover_sources(
        self, queries: Sequence[str], *, allowed_domains: Sequence[str] | None = None
    ) -> list[Source]:
        raise NotImplementedError

    async def enrich_company(
        self, *, name: str, domain: str | None, page_text: str | None
    ) -> EnrichResult:
        self.calls.append({"name": name, "domain": domain, "page_text": page_text})
        return self._result

    async def extract_posting(
        self, *, page_text: str, company_name: str | None = None
    ) -> ExtractionResult:
        if self._extract_result is None:
            raise NotImplementedError
        return self._extract_result

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.1] * 1536 for _ in texts]

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


# --- enrich_company -----------------------------------------------------------


@requires_db
async def test_enrich_company_prefers_llm_values_and_detects_ats(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = Company(user_id=user.id, name="Acme", domain="acme.com", hq_country="US")
    db_session.add(company)
    await db_session.flush()

    openai = _StubOpenAI(
        EnrichResult(
            hq_country="CA",
            hq_confidence=80,
            comp_estimate="$100k-$150k",
            careers_url="https://boards.greenhouse.io/acme",
            ats=None,
        )
    )
    fetcher = _StubFetcher(FetchedDoc(url="https://acme.com", status=200, text="hello"))

    result = await enrich_company(company, _deps(openai, fetcher))

    assert result.hq_country == "CA"  # LLM value wins over existing "US"
    assert result.hq_confidence == 80
    assert result.comp_estimate == "$100k-$150k"
    assert result.careers_url == "https://boards.greenhouse.io/acme"
    assert result.ats == "greenhouse"  # detect_ats applied from the careers_url host
    assert fetcher.calls == ["https://acme.com"]  # no careers_url yet -> falls back to domain
    assert openai.calls == [{"name": "Acme", "domain": "acme.com", "page_text": "hello"}]


@requires_db
async def test_enrich_company_passes_html_reduced_page_text_to_llm(
    db_session: AsyncSession,
) -> None:
    """The fetched page is reduced via html_to_text() before it reaches the LLM — raw HTML
    overflowed the 128k context on a real run (context_length_exceeded)."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = Company(user_id=user.id, name="Acme", domain="acme.com")
    db_session.add(company)
    await db_session.flush()

    html = (
        "<html><body>"
        "<script>track();</script>"
        "<h1>Acme Corp</h1>"
        "<p>We build   distributed   systems.</p>"
        "</body></html>"
    )
    openai = _StubOpenAI(EnrichResult())
    fetcher = _StubFetcher(FetchedDoc(url="https://acme.com", status=200, text=html))

    await enrich_company(company, _deps(openai, fetcher))

    assert openai.calls == [
        {
            "name": "Acme",
            "domain": "acme.com",
            "page_text": "Acme Corp We build distributed systems.",
        }
    ]


@requires_db
async def test_enrich_company_falls_back_to_existing_company_fields(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = Company(
        user_id=user.id,
        name="Acme",
        domain="acme.com",
        hq_country="US",
        careers_url="https://acme.com/careers",
        ats="lever",
    )
    db_session.add(company)
    await db_session.flush()

    openai = _StubOpenAI(EnrichResult())  # LLM has nothing to add
    fetcher = _StubFetcher(FetchedDoc(url="https://acme.com/careers", status=404, text=""))

    result = await enrich_company(company, _deps(openai, fetcher))

    assert result.hq_country == "US"  # falls back to existing company field
    assert result.careers_url == "https://acme.com/careers"  # falls back
    assert result.ats == "lever"  # detect_ats(ats_hint=company.ats) applied
    assert fetcher.calls == ["https://acme.com/careers"]  # careers_url preferred over domain
    assert openai.calls[0]["page_text"] is None  # non-200 status tolerated, no page text


# --- ingest_company -------------------------------------------------------------


@requires_db
async def test_ingest_company_applies_enrichment_and_defaults_logo_to_favicon(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = Company(user_id=user.id, name="Acme", domain="acme.com")
    db_session.add(company)
    await db_session.flush()
    company_id = company.id

    openai = _StubOpenAI(
        EnrichResult(
            hq_country="US",
            hq_confidence=85,
            comp_estimate="$140k-$190k",
            careers_url="https://acme.com/careers",
            ats="greenhouse",
        )
    )
    fetcher = _StubFetcher(FetchedDoc(url="https://acme.com", status=404, text=""))

    await ingest_company(db_session, user.id, company_id, _deps(openai, fetcher))

    refreshed = await db_session.get(Company, company_id)
    assert refreshed is not None
    assert refreshed.hq_country == "US"
    assert refreshed.hq_confidence == 85
    assert refreshed.comp_estimate == "$140k-$190k"
    assert refreshed.careers_url == "https://acme.com/careers"
    assert refreshed.ats == "greenhouse"
    assert refreshed.logo_url == "https://icons.duckduckgo.com/ip3/acme.com.ico"


@requires_db
async def test_ingest_company_keeps_the_discovered_careers_url_over_the_models_guess(
    db_session: AsyncSession,
) -> None:
    """Discovery's careers_url is observed fact; the model's is a guess.

    Letting the guess win would discard the real URL permanently — every later run would then
    enrich from the guess, and for a path-token ATS the `https://{domain}` fallback is a
    fabricated host that does not resolve at all.
    """
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    discovered = "https://job-boards.greenhouse.io/acme/jobs/123"
    company = Company(
        user_id=user.id,
        name="Acme",
        domain="acme.job-boards.greenhouse.io",
        careers_url=discovered,
    )
    db_session.add(company)
    await db_session.flush()
    company_id = company.id

    openai = _StubOpenAI(
        EnrichResult(hq_country="US", careers_url="https://acme.example/careers-guess")
    )
    fetcher = _StubFetcher(FetchedDoc(url=discovered, status=200, text="<html>Acme</html>"))

    await ingest_company(db_session, user.id, company_id, _deps(openai, fetcher))

    refreshed = await db_session.get(Company, company_id)
    assert refreshed is not None
    assert refreshed.careers_url == discovered  # not the guess
    assert refreshed.hq_country == "US"  # other enriched fields still apply
    assert fetcher.calls[0] == discovered  # and the real page is what got fetched


@requires_db
async def test_ingest_company_does_not_overwrite_existing_logo(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = Company(
        user_id=user.id,
        name="Acme",
        domain="acme.com",
        logo_url="https://existing.example/logo.png",
    )
    db_session.add(company)
    await db_session.flush()
    company_id = company.id

    openai = _StubOpenAI(EnrichResult())
    fetcher = _StubFetcher(FetchedDoc(url="https://acme.com", status=404, text=""))

    await ingest_company(db_session, user.id, company_id, _deps(openai, fetcher))

    refreshed = await db_session.get(Company, company_id)
    assert refreshed is not None
    assert refreshed.logo_url == "https://existing.example/logo.png"


@requires_db
async def test_ingest_company_is_noop_for_non_owned_company(db_session: AsyncSession) -> None:
    owner = await make_user(db_session)
    other = await make_user(db_session)
    await set_tenant(db_session, owner.id)
    company = Company(user_id=owner.id, name="Acme", domain="acme.com")
    db_session.add(company)
    await db_session.flush()
    company_id = company.id

    openai = _StubOpenAI(EnrichResult(hq_country="US"))
    fetcher = _StubFetcher(FetchedDoc(url="https://acme.com", status=404, text=""))

    # GUC stays set to the owner (so RLS lets the row through) — the mismatched
    # `user_id` argument exercises ingest_company's own ownership check.
    await ingest_company(db_session, other.id, company_id, _deps(openai, fetcher))

    assert openai.calls == []
    assert fetcher.calls == []
    refreshed = await db_session.get(Company, company_id)
    assert refreshed is not None
    assert refreshed.hq_country is None


@requires_db
async def test_ingest_company_extracts_and_embeds_shell_postings_after_fetch(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = Company(user_id=user.id, name="Acme", domain="acme.com")
    db_session.add(company)
    await db_session.flush()
    company_id = company.id

    shell = Posting(
        user_id=user.id,
        company_id=company.id,
        source="scrape",
        source_url="https://acme.com/jobs/1",
        content_hash="shell-1",
    )
    db_session.add(shell)
    await db_session.flush()
    shell_id = shell.id

    extract_result = ExtractionResult(
        title="Senior Backend Engineer", required_skills=["Python"], extraction_confidence=80
    )
    openai = _StubOpenAI(EnrichResult(), extract_result=extract_result)
    fetcher = _StubFetcher(
        FetchedDoc(
            url="https://acme.com/jobs/1",
            status=200,
            text=_JOB_PAGE_TEXT,
        )
    )

    await ingest_company(db_session, user.id, company_id, _deps(openai, fetcher))

    refreshed = await db_session.get(Posting, shell_id)
    assert refreshed is not None
    assert refreshed.title == "Senior Backend Engineer"
    assert refreshed.extraction_confidence == 80
    assert refreshed.title_vec is not None
    assert len(refreshed.title_vec) == 1536
    assert refreshed.skills_vec is not None
    assert len(refreshed.skills_vec) == 1536


@requires_db
async def test_ingest_company_caps_llm_extraction_at_ingest_max_postings(
    db_session: AsyncSession,
) -> None:
    """A big board can leave hundreds of shells needing extraction; ingest_company must only
    LLM-extract `settings.ingest_max_postings` of them per run (a 662-job board would otherwise
    fire 600+ extraction calls) — the most-recently-seen shells go first, the rest stay
    `title IS NULL` for a later run to pick up."""
    user = await make_user(db_session)
    await set_tenant(db_session, user.id)
    company = Company(user_id=user.id, name="Acme", domain="acme.com")
    db_session.add(company)
    await db_session.flush()
    company_id = company.id

    shells = [
        Posting(
            user_id=user.id,
            company_id=company.id,
            source="scrape",
            source_url=f"https://acme.com/jobs/{i}",
            content_hash=f"shell-{i}",
            first_seen_at=datetime(2026, 7, i + 1, tzinfo=UTC),
        )
        for i in range(3)
    ]
    db_session.add_all(shells)
    await db_session.flush()
    oldest_id, middle_id, newest_id = (s.id for s in shells)  # first_seen_at ascending

    extract_result = ExtractionResult(
        title="Senior Backend Engineer", required_skills=["Python"], extraction_confidence=80
    )
    openai = _StubOpenAI(EnrichResult(), extract_result=extract_result)
    fetcher = _StubFetcher(
        FetchedDoc(
            url="https://acme.com/jobs/0",
            status=200,
            text=_JOB_PAGE_TEXT,
        )
    )
    deps = PipelineDeps(
        openai=openai,
        fetcher=fetcher,
        settings=Settings(ingest_max_postings=2),
        now=lambda: datetime(2026, 7, 10, tzinfo=UTC),
    )

    await ingest_company(db_session, user.id, company_id, deps)

    newest = await db_session.get(Posting, newest_id)
    middle = await db_session.get(Posting, middle_id)
    oldest = await db_session.get(Posting, oldest_id)
    assert newest is not None
    assert middle is not None
    assert oldest is not None
    assert newest.title is not None  # extracted
    assert middle.title is not None  # extracted
    assert oldest.title is None  # left for a later run — cap of 2 hit
