from dataclasses import dataclass
from pathlib import Path

import pytest

from specula_api.db.models import Company
from specula_api.pipeline.http import Disallowed, FetchedDoc, RecordedFetcher
from specula_api.pipeline.source import (
    AshbyAdapter,
    BoardUnavailable,
    GenericHtmlAdapter,
    GreenhouseAdapter,
    LeverAdapter,
    PersonioAdapter,
    RecruiteeAdapter,
    SmartRecruitersAdapter,
    WorkableAdapter,
    detect_ats,
    resolve_adapter,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pipeline"
ATS_FIXTURES_DIR = FIXTURES_DIR / "ats"


@dataclass
class _CompanyStub:
    domain: str | None = None
    careers_url: str | None = None
    ats: str | None = None


class _StubFetcher:
    """Returns a fixed body for every URL requested; records calls made."""

    def __init__(
        self, body: str, *, status: int = 200, content_type: str = "application/json"
    ) -> None:
        self._body = body
        self._status = status
        self._content_type = content_type
        self.calls: list[str] = []

    async def get(self, url: str, *, accept: str = "text/html") -> FetchedDoc:
        self.calls.append(url)
        return FetchedDoc(
            url=url, status=self._status, text=self._body, content_type=self._content_type
        )

    async def aclose(self) -> None:
        return None


class _DisallowedFetcher:
    """robots.txt forbids every URL — what a disallowed ATS host looks like to an adapter."""

    async def get(self, url: str, *, accept: str = "text/html") -> FetchedDoc:
        raise Disallowed(url)

    async def aclose(self) -> None:
        return None


# --- detect_ats -------------------------------------------------------------


def test_detect_ats_prefers_explicit_hint() -> None:
    assert detect_ats(domain=None, careers_url=None, ats_hint="Greenhouse") == "greenhouse"


@pytest.mark.parametrize(
    ("careers_url", "expected"),
    [
        ("https://boards.greenhouse.io/acme", "greenhouse"),
        ("https://jobs.lever.co/acme", "lever"),
        ("https://jobs.ashbyhq.com/acme", "ashby"),
        ("https://jobs.smartrecruiters.com/Acme", "smartrecruiters"),
        ("https://acme.recruitee.com/", "recruitee"),
        ("https://apply.workable.com/acme/", "workable"),
        ("https://acme.jobs.personio.de/", "personio"),
        ("https://acme.jobs.personio.com/", "personio"),
    ],
)
def test_detect_ats_from_careers_url_host(careers_url: str, expected: str) -> None:
    assert detect_ats(domain=None, careers_url=careers_url, ats_hint=None) == expected


def test_detect_ats_returns_none_for_unknown_host() -> None:
    assert (
        detect_ats(domain="acme.com", careers_url="https://acme.com/careers", ats_hint=None) is None
    )


def test_detect_ats_returns_none_when_nothing_given() -> None:
    assert detect_ats(domain=None, careers_url=None, ats_hint=None) is None


# --- resolve_adapter ----------------------------------------------------------


def test_resolve_adapter_picks_greenhouse() -> None:
    company = _CompanyStub(careers_url="https://boards.greenhouse.io/acme")
    assert resolve_adapter(company).ats == "greenhouse"


def test_resolve_adapter_picks_lever() -> None:
    company = _CompanyStub(ats="lever")
    assert resolve_adapter(company).ats == "lever"


def test_resolve_adapter_picks_ashby() -> None:
    company = _CompanyStub(careers_url="https://jobs.ashbyhq.com/acme")
    assert resolve_adapter(company).ats == "ashby"


def test_resolve_adapter_picks_smartrecruiters() -> None:
    company = _CompanyStub(careers_url="https://jobs.smartrecruiters.com/Acme")
    assert resolve_adapter(company).ats == "smartrecruiters"


def test_resolve_adapter_picks_recruitee() -> None:
    company = _CompanyStub(careers_url="https://acme.recruitee.com/")
    assert resolve_adapter(company).ats == "recruitee"


def test_resolve_adapter_picks_workable() -> None:
    company = _CompanyStub(careers_url="https://apply.workable.com/acme/")
    assert resolve_adapter(company).ats == "workable"


def test_resolve_adapter_picks_personio() -> None:
    company = _CompanyStub(careers_url="https://acme.jobs.personio.de/")
    assert resolve_adapter(company).ats == "personio"


def test_resolve_adapter_falls_back_to_generic() -> None:
    company = _CompanyStub(domain="acme.com", careers_url="https://acme.com/careers")
    assert resolve_adapter(company).ats == "generic"


def test_resolve_adapter_accepts_an_unsaved_company_model() -> None:
    # CompanyLike is structural: a real (unsaved, no DB) Company model instance satisfies it too.
    company = Company(name="Acme", careers_url="https://boards.greenhouse.io/acme")
    assert resolve_adapter(company).ats == "greenhouse"


# --- GreenhouseAdapter --------------------------------------------------------


async def test_greenhouse_adapter_parses_fixture_feed() -> None:
    body = (ATS_FIXTURES_DIR / "greenhouse" / "jobs.json").read_text()
    company = _CompanyStub(careers_url="https://boards.greenhouse.io/acme")

    postings = await GreenhouseAdapter().list_postings(company, _StubFetcher(body))

    assert len(postings) == 3
    first = postings[0]
    assert first.source_url == "https://boards.greenhouse.io/acme/jobs/4123456"
    assert first.external_id == "4123456"
    assert first.title_hint == "Senior Backend Engineer"
    assert len(first.content_hash) == 64


async def test_greenhouse_adapter_content_hash_is_stable_across_runs() -> None:
    body = (ATS_FIXTURES_DIR / "greenhouse" / "jobs.json").read_text()
    company = _CompanyStub(careers_url="https://boards.greenhouse.io/acme")

    first_run = await GreenhouseAdapter().list_postings(company, _StubFetcher(body))
    second_run = await GreenhouseAdapter().list_postings(company, _StubFetcher(body))

    assert [p.content_hash for p in first_run] == [p.content_hash for p in second_run]


async def test_greenhouse_adapter_derives_token_from_an_ats_host_domain() -> None:
    body = (ATS_FIXTURES_DIR / "greenhouse" / "jobs.json").read_text()
    company = _CompanyStub(domain="acme.job-boards.greenhouse.io")
    fetcher = _StubFetcher(body)

    postings = await GreenhouseAdapter().list_postings(company, fetcher)

    assert len(postings) == 3
    assert fetcher.calls == ["https://boards-api.greenhouse.io/v1/boards/acme/jobs"]


@pytest.mark.parametrize("status", [0, 404, 429, 503])
async def test_greenhouse_adapter_raises_when_the_board_cannot_be_read(status: int) -> None:
    """An unreadable board must not be indistinguishable from an empty one.

    `[]` means "read the board, it lists nothing", which makes fetch_postings retire every
    still-open posting for the company. A transport failure (status=0 is PoliteFetcher's
    sentinel for DNS/timeout/reset), a 404 board token or a throttled 429 tell us nothing
    about what's open, so they must surface as an error instead.
    """
    company = _CompanyStub(careers_url="https://boards.greenhouse.io/acme")
    with pytest.raises(BoardUnavailable):
        await GreenhouseAdapter().list_postings(company, _StubFetcher("", status=status))


async def test_greenhouse_adapter_raises_on_garbage_feed() -> None:
    company = _CompanyStub(careers_url="https://boards.greenhouse.io/acme")
    with pytest.raises(BoardUnavailable):
        await GreenhouseAdapter().list_postings(company, _StubFetcher("not json"))


async def test_greenhouse_adapter_raises_when_robots_disallows() -> None:
    """The live SmartRecruiters case: robots forbids the board, so we learn nothing about it."""
    company = _CompanyStub(careers_url="https://boards.greenhouse.io/acme")
    with pytest.raises(BoardUnavailable):
        await GreenhouseAdapter().list_postings(company, _DisallowedFetcher())


async def test_greenhouse_adapter_returns_empty_for_a_genuinely_empty_board() -> None:
    """The one case that legitimately yields []: a 200 answered with no jobs. Only this may
    close out the company's postings."""
    company = _CompanyStub(careers_url="https://boards.greenhouse.io/acme")
    assert await GreenhouseAdapter().list_postings(company, _StubFetcher('{"jobs": []}')) == []


async def test_greenhouse_adapter_raises_without_a_derivable_token() -> None:
    company = _CompanyStub()
    fetcher = _StubFetcher((ATS_FIXTURES_DIR / "greenhouse" / "jobs.json").read_text())

    with pytest.raises(BoardUnavailable):
        await GreenhouseAdapter().list_postings(company, fetcher)

    assert fetcher.calls == []


# --- LeverAdapter --------------------------------------------------------------


async def test_lever_adapter_parses_fixture_feed() -> None:
    body = (ATS_FIXTURES_DIR / "lever" / "postings.json").read_text()
    company = _CompanyStub(careers_url="https://jobs.lever.co/acme")

    postings = await LeverAdapter().list_postings(company, _StubFetcher(body))

    assert len(postings) == 2
    first = postings[0]
    assert first.source_url == "https://jobs.lever.co/acme/5f2b1e2a-1111-4a2b-9c3d-abcdef123456"
    assert first.external_id == "5f2b1e2a-1111-4a2b-9c3d-abcdef123456"
    assert first.title_hint == "Software Engineer, Infrastructure"


async def test_lever_adapter_content_hash_is_stable_across_runs() -> None:
    body = (ATS_FIXTURES_DIR / "lever" / "postings.json").read_text()
    company = _CompanyStub(careers_url="https://jobs.lever.co/acme")

    first_run = await LeverAdapter().list_postings(company, _StubFetcher(body))
    second_run = await LeverAdapter().list_postings(company, _StubFetcher(body))

    assert [p.content_hash for p in first_run] == [p.content_hash for p in second_run]


async def test_lever_adapter_raises_on_404() -> None:
    company = _CompanyStub(careers_url="https://jobs.lever.co/acme")
    with pytest.raises(BoardUnavailable):
        await LeverAdapter().list_postings(company, _StubFetcher("", status=404))


async def test_lever_adapter_raises_on_garbage_feed() -> None:
    company = _CompanyStub(careers_url="https://jobs.lever.co/acme")
    with pytest.raises(BoardUnavailable):
        await LeverAdapter().list_postings(company, _StubFetcher("<html>nope</html>"))


# --- AshbyAdapter ----------------------------------------------------------------


async def test_ashby_adapter_parses_fixture_feed() -> None:
    body = (ATS_FIXTURES_DIR / "ashby" / "job-board.json").read_text()
    company = _CompanyStub(careers_url="https://jobs.ashbyhq.com/acme")

    postings = await AshbyAdapter().list_postings(company, _StubFetcher(body))

    assert len(postings) == 3
    first = postings[0]
    assert first.source_url == "https://jobs.ashbyhq.com/acme/b6f1c2e0-3333-4b3c-8d4e-abcdef654321"
    assert first.external_id == "b6f1c2e0-3333-4b3c-8d4e-abcdef654321"
    assert first.title_hint == "Engineering Manager, Payments"


async def test_ashby_adapter_content_hash_is_stable_across_runs() -> None:
    body = (ATS_FIXTURES_DIR / "ashby" / "job-board.json").read_text()
    company = _CompanyStub(careers_url="https://jobs.ashbyhq.com/acme")

    first_run = await AshbyAdapter().list_postings(company, _StubFetcher(body))
    second_run = await AshbyAdapter().list_postings(company, _StubFetcher(body))

    assert [p.content_hash for p in first_run] == [p.content_hash for p in second_run]


async def test_ashby_adapter_raises_on_404() -> None:
    company = _CompanyStub(careers_url="https://jobs.ashbyhq.com/acme")
    with pytest.raises(BoardUnavailable):
        await AshbyAdapter().list_postings(company, _StubFetcher("", status=404))


async def test_ashby_adapter_raises_on_garbage_feed() -> None:
    company = _CompanyStub(careers_url="https://jobs.ashbyhq.com/acme")
    with pytest.raises(BoardUnavailable):
        await AshbyAdapter().list_postings(company, _StubFetcher("{not valid"))


# --- SmartRecruitersAdapter --------------------------------------------------------


async def test_smartrecruiters_adapter_parses_fixture_feed() -> None:
    body = (ATS_FIXTURES_DIR / "smartrecruiters" / "postings.json").read_text()
    company = _CompanyStub(careers_url="https://jobs.smartrecruiters.com/DeliveryHero")

    postings = await SmartRecruitersAdapter().list_postings(company, _StubFetcher(body))

    assert len(postings) == 3
    first = postings[0]
    assert first.source_url == "https://jobs.smartrecruiters.com/DeliveryHero/744000138833829"
    assert first.external_id == "744000138833829"
    assert first.title_hint == "Product Manager - Customer Data Platform, Tech Foundations"
    assert len(first.content_hash) == 64


async def test_smartrecruiters_adapter_content_hash_is_stable_across_runs() -> None:
    body = (ATS_FIXTURES_DIR / "smartrecruiters" / "postings.json").read_text()
    company = _CompanyStub(careers_url="https://jobs.smartrecruiters.com/DeliveryHero")

    first_run = await SmartRecruitersAdapter().list_postings(company, _StubFetcher(body))
    second_run = await SmartRecruitersAdapter().list_postings(company, _StubFetcher(body))

    assert [p.content_hash for p in first_run] == [p.content_hash for p in second_run]


async def test_smartrecruiters_adapter_derives_token_from_an_ats_host_domain() -> None:
    body = (ATS_FIXTURES_DIR / "smartrecruiters" / "postings.json").read_text()
    company = _CompanyStub(domain="deliveryhero.jobs.smartrecruiters.com")
    fetcher = _StubFetcher(body)

    postings = await SmartRecruitersAdapter().list_postings(company, fetcher)

    assert len(postings) == 3
    assert fetcher.calls == ["https://api.smartrecruiters.com/v1/companies/deliveryhero/postings"]


async def test_smartrecruiters_adapter_raises_on_404() -> None:
    company = _CompanyStub(careers_url="https://jobs.smartrecruiters.com/DeliveryHero")
    with pytest.raises(BoardUnavailable):
        await SmartRecruitersAdapter().list_postings(company, _StubFetcher("", status=404))


async def test_smartrecruiters_adapter_raises_on_garbage_feed() -> None:
    company = _CompanyStub(careers_url="https://jobs.smartrecruiters.com/DeliveryHero")
    with pytest.raises(BoardUnavailable):
        await SmartRecruitersAdapter().list_postings(company, _StubFetcher("not json"))


async def test_smartrecruiters_adapter_raises_without_a_derivable_token() -> None:
    company = _CompanyStub()
    fetcher = _StubFetcher((ATS_FIXTURES_DIR / "smartrecruiters" / "postings.json").read_text())

    with pytest.raises(BoardUnavailable):
        await SmartRecruitersAdapter().list_postings(company, fetcher)

    assert fetcher.calls == []


# --- RecruiteeAdapter ---------------------------------------------------------------


async def test_recruitee_adapter_parses_fixture_feed() -> None:
    body = (ATS_FIXTURES_DIR / "recruitee" / "offers.json").read_text()
    company = _CompanyStub(careers_url="https://bunq.recruitee.com/")

    postings = await RecruiteeAdapter().list_postings(company, _StubFetcher(body))

    assert len(postings) == 3
    first = postings[0]
    assert first.source_url == "https://careers.bunq.com/o/operational-risk-intern-1"
    assert first.external_id == "2679762"
    assert first.title_hint == "Operational Risk Intern"
    assert len(first.content_hash) == 64


async def test_recruitee_adapter_content_hash_is_stable_across_runs() -> None:
    body = (ATS_FIXTURES_DIR / "recruitee" / "offers.json").read_text()
    company = _CompanyStub(careers_url="https://bunq.recruitee.com/")

    first_run = await RecruiteeAdapter().list_postings(company, _StubFetcher(body))
    second_run = await RecruiteeAdapter().list_postings(company, _StubFetcher(body))

    assert [p.content_hash for p in first_run] == [p.content_hash for p in second_run]


async def test_recruitee_adapter_derives_token_from_subdomain_not_path() -> None:
    """The token lives in the subdomain (bunq.recruitee.com), not the job page's path
    (/o/some-job) — unlike the path-token boards (Greenhouse/Lever/Ashby/SmartRecruiters/
    Workable), so a job-specific careers_url must not be mistaken for a path token ("o")."""
    body = (ATS_FIXTURES_DIR / "recruitee" / "offers.json").read_text()
    company = _CompanyStub(careers_url="https://bunq.recruitee.com/o/some-other-job")
    fetcher = _StubFetcher(body)

    postings = await RecruiteeAdapter().list_postings(company, fetcher)

    assert len(postings) == 3
    assert fetcher.calls == ["https://bunq.recruitee.com/api/offers/"]


async def test_recruitee_adapter_raises_on_404() -> None:
    company = _CompanyStub(careers_url="https://bunq.recruitee.com/")
    with pytest.raises(BoardUnavailable):
        await RecruiteeAdapter().list_postings(company, _StubFetcher("", status=404))


async def test_recruitee_adapter_raises_on_garbage_feed() -> None:
    company = _CompanyStub(careers_url="https://bunq.recruitee.com/")
    with pytest.raises(BoardUnavailable):
        await RecruiteeAdapter().list_postings(company, _StubFetcher("not json"))


async def test_recruitee_adapter_raises_without_a_derivable_token() -> None:
    company = _CompanyStub()
    fetcher = _StubFetcher((ATS_FIXTURES_DIR / "recruitee" / "offers.json").read_text())

    with pytest.raises(BoardUnavailable):
        await RecruiteeAdapter().list_postings(company, fetcher)

    assert fetcher.calls == []


# --- WorkableAdapter -----------------------------------------------------------------


async def test_workable_adapter_parses_fixture_feed() -> None:
    body = (ATS_FIXTURES_DIR / "workable" / "widget.json").read_text()
    company = _CompanyStub(careers_url="https://apply.workable.com/mondu/")

    postings = await WorkableAdapter().list_postings(company, _StubFetcher(body))

    assert len(postings) == 3
    first = postings[0]
    assert first.source_url == "https://apply.workable.com/j/4E3D7171DF"
    assert first.external_id == "4E3D7171DF"
    assert first.title_hint == "(Senior) Sales Manager, French Market"
    assert len(first.content_hash) == 64


async def test_workable_adapter_content_hash_is_stable_across_runs() -> None:
    body = (ATS_FIXTURES_DIR / "workable" / "widget.json").read_text()
    company = _CompanyStub(careers_url="https://apply.workable.com/mondu/")

    first_run = await WorkableAdapter().list_postings(company, _StubFetcher(body))
    second_run = await WorkableAdapter().list_postings(company, _StubFetcher(body))

    assert [p.content_hash for p in first_run] == [p.content_hash for p in second_run]


async def test_workable_adapter_derives_token_from_an_ats_host_domain() -> None:
    body = (ATS_FIXTURES_DIR / "workable" / "widget.json").read_text()
    company = _CompanyStub(domain="mondu.apply.workable.com")
    fetcher = _StubFetcher(body)

    postings = await WorkableAdapter().list_postings(company, fetcher)

    assert len(postings) == 3
    assert fetcher.calls == ["https://apply.workable.com/api/v1/widget/accounts/mondu?details=true"]


async def test_workable_adapter_raises_on_404() -> None:
    company = _CompanyStub(careers_url="https://apply.workable.com/mondu/")
    with pytest.raises(BoardUnavailable):
        await WorkableAdapter().list_postings(company, _StubFetcher("", status=404))


async def test_workable_adapter_raises_on_garbage_feed() -> None:
    company = _CompanyStub(careers_url="https://apply.workable.com/mondu/")
    with pytest.raises(BoardUnavailable):
        await WorkableAdapter().list_postings(company, _StubFetcher("not json"))


async def test_workable_adapter_raises_without_a_derivable_token() -> None:
    company = _CompanyStub()
    fetcher = _StubFetcher((ATS_FIXTURES_DIR / "workable" / "widget.json").read_text())

    with pytest.raises(BoardUnavailable):
        await WorkableAdapter().list_postings(company, fetcher)

    assert fetcher.calls == []


# --- PersonioAdapter -----------------------------------------------------------------


async def test_personio_adapter_parses_fixture_feed() -> None:
    body = (ATS_FIXTURES_DIR / "personio" / "jobs.xml").read_text()
    company = _CompanyStub(careers_url="https://smava.jobs.personio.de/")

    postings = await PersonioAdapter().list_postings(
        company, _StubFetcher(body, content_type="text/xml")
    )

    assert len(postings) == 2
    first = postings[0]
    assert first.source_url == "https://smava.jobs.personio.de/job/275560"
    assert first.external_id == "275560"
    assert first.title_hint == "Initiativbewerbung (Festanstellung)"
    assert len(first.content_hash) == 64


async def test_personio_adapter_content_hash_is_stable_across_runs() -> None:
    body = (ATS_FIXTURES_DIR / "personio" / "jobs.xml").read_text()
    company = _CompanyStub(careers_url="https://smava.jobs.personio.de/")

    first_run = await PersonioAdapter().list_postings(
        company, _StubFetcher(body, content_type="text/xml")
    )
    second_run = await PersonioAdapter().list_postings(
        company, _StubFetcher(body, content_type="text/xml")
    )

    assert [p.content_hash for p in first_run] == [p.content_hash for p in second_run]


async def test_personio_adapter_derives_token_from_an_ats_host_domain() -> None:
    """The token lives in the subdomain (smava.jobs.personio.de), same family as Recruitee —
    falling back to the company's plain domain must still resolve the right feed URL."""
    body = (ATS_FIXTURES_DIR / "personio" / "jobs.xml").read_text()
    company = _CompanyStub(domain="smava.jobs.personio.de")
    fetcher = _StubFetcher(body, content_type="text/xml")

    postings = await PersonioAdapter().list_postings(company, fetcher)

    assert len(postings) == 2
    assert fetcher.calls == ["https://smava.jobs.personio.de/xml"]


async def test_personio_adapter_raises_on_404() -> None:
    company = _CompanyStub(careers_url="https://smava.jobs.personio.de/")
    with pytest.raises(BoardUnavailable):
        await PersonioAdapter().list_postings(company, _StubFetcher("", status=404))


async def test_personio_adapter_raises_on_garbage_feed() -> None:
    company = _CompanyStub(careers_url="https://smava.jobs.personio.de/")
    with pytest.raises(BoardUnavailable):
        await PersonioAdapter().list_postings(
            company, _StubFetcher("not xml at all", content_type="text/xml")
        )


async def test_personio_adapter_raises_without_a_derivable_token() -> None:
    company = _CompanyStub()
    fetcher = _StubFetcher((ATS_FIXTURES_DIR / "personio" / "jobs.xml").read_text())

    with pytest.raises(BoardUnavailable):
        await PersonioAdapter().list_postings(company, fetcher)

    assert fetcher.calls == []


# --- GenericHtmlAdapter -----------------------------------------------------------


async def test_generic_html_adapter_parses_job_links_from_careers_page() -> None:
    company = _CompanyStub(careers_url="https://www.acmecorp.example/careers")
    fetcher = RecordedFetcher(FIXTURES_DIR)

    postings = await GenericHtmlAdapter().list_postings(company, fetcher)

    assert len(postings) == 2
    urls = {p.source_url for p in postings}
    assert urls == {
        "https://boards.greenhouse.io/acmecorp/jobs/4123456",
        "https://www.acmecorp.example/careers/openings/platform-pm",
    }
    titles = {p.title_hint for p in postings}
    assert titles == {"Senior Backend Engineer", "Product Manager, Platform"}


async def test_generic_html_adapter_returns_empty_for_js_rendered_shell() -> None:
    company = _CompanyStub(careers_url="https://www.acmecorp.example/spa-careers")
    fetcher = RecordedFetcher(FIXTURES_DIR)

    postings = await GenericHtmlAdapter().list_postings(company, fetcher)

    assert postings == []


async def test_generic_html_adapter_raises_on_fixture_miss() -> None:
    company = _CompanyStub(careers_url="https://unknown.example/careers")
    fetcher = RecordedFetcher(FIXTURES_DIR)

    with pytest.raises(BoardUnavailable):
        await GenericHtmlAdapter().list_postings(company, fetcher)


async def test_generic_html_adapter_returns_empty_without_careers_url() -> None:
    company = _CompanyStub()
    postings = await GenericHtmlAdapter().list_postings(company, RecordedFetcher(FIXTURES_DIR))
    assert postings == []


# --- board-token derivation must be host-verified -------------------------------


async def test_token_is_not_invented_from_an_unrelated_company_domain() -> None:
    """enrich feeds an LLM-guessed `ats` into detect_ats, which trusts it. Deriving the board
    token from a bare domain label would then query a stranger's board: monday.com + a guessed
    "workable" hits apply.workable.com/.../monday, and whoever owns that slug gets ingested as
    this company. The domain may only supply a token when it IS on the ATS host."""
    company = _CompanyStub(domain="monday.com", careers_url="https://monday.com/careers")
    fetcher = _StubFetcher('{"jobs": []}')

    with pytest.raises(BoardUnavailable):
        await WorkableAdapter().list_postings(company, fetcher)

    assert fetcher.calls == []  # never went looking


async def test_no_derivable_token_raises_rather_than_looking_empty() -> None:
    """Same reasoning as BoardUnavailable elsewhere: we never addressed a board, so we know
    nothing about it — returning [] would retire every posting the company has."""
    company = _CompanyStub(domain="acme.com")
    fetcher = _StubFetcher('{"jobs": []}')

    with pytest.raises(BoardUnavailable):
        await GreenhouseAdapter().list_postings(company, fetcher)

    assert fetcher.calls == []


# --- generic scrape must not turn page furniture into postings -------------------


_CAREERS_HTML = """
<html><body>
  <a href="#jobs">Jobs</a>
  <a href="#open-positions">Open positions</a>
  <a href="mailto:careers@acme.example">Email us</a>
  <a href="javascript:openJob()">Apply</a>
  <a href="/careers">Careers</a>
  <a href="/careers/staff-engineer">Staff Engineer</a>
  <a href="/careers/staff-engineer?utm_source=x">Staff Engineer (tracked)</a>
  <a href="https://www.linkedin.com/company/acme/jobs">Our LinkedIn jobs</a>
  <a href="https://boards.greenhouse.io/acme/jobs/42">Data Scientist</a>
</body></html>
"""


async def test_generic_adapter_keeps_only_real_job_links() -> None:
    company = _CompanyStub(careers_url="https://acme.example/careers")

    postings = await GenericHtmlAdapter().list_postings(
        company, _StubFetcher(_CAREERS_HTML, content_type="text/html")
    )

    urls = {p.source_url for p in postings}
    assert urls == {
        "https://acme.example/careers/staff-engineer",  # same host, real job path
        "https://boards.greenhouse.io/acme/jobs/42",  # known ATS host
    }


@pytest.mark.parametrize(
    ("href", "why"),
    [
        ("#jobs", "fragment-only anchor is the same page"),
        ("mailto:careers@acme.example", "not an http(s) target"),
        ("javascript:openJob()", "not an http(s) target"),
        ("/careers", "the careers page itself is not a posting"),
        ("https://www.linkedin.com/company/acme/jobs", "third-party host"),
    ],
)
async def test_generic_adapter_excludes_page_furniture(href: str, why: str) -> None:
    company = _CompanyStub(careers_url="https://acme.example/careers")
    html = f'<html><body><a href="{href}">x</a></body></html>'

    postings = await GenericHtmlAdapter().list_postings(
        company, _StubFetcher(html, content_type="text/html")
    )

    assert postings == [], why


async def test_generic_adapter_collapses_query_string_duplicates() -> None:
    """Same job, two hrefs — one tracked. Distinct content_hashes would double-count it and
    burn the per-company extraction budget twice."""
    company = _CompanyStub(careers_url="https://acme.example/careers")
    html = (
        '<html><body><a href="/careers/eng">Eng</a>'
        '<a href="/careers/eng?utm_source=x">Eng</a></body></html>'
    )

    postings = await GenericHtmlAdapter().list_postings(
        company, _StubFetcher(html, content_type="text/html")
    )

    assert len(postings) == 1
