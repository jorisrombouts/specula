from dataclasses import dataclass
from pathlib import Path

import pytest

from specula_api.db.models import Company
from specula_api.pipeline.http import FetchedDoc, RecordedFetcher
from specula_api.pipeline.source import (
    AshbyAdapter,
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


async def test_greenhouse_adapter_derives_token_from_domain_fallback() -> None:
    body = (ATS_FIXTURES_DIR / "greenhouse" / "jobs.json").read_text()
    company = _CompanyStub(domain="acme.com")
    fetcher = _StubFetcher(body)

    postings = await GreenhouseAdapter().list_postings(company, fetcher)

    assert len(postings) == 3
    assert fetcher.calls == ["https://boards-api.greenhouse.io/v1/boards/acme/jobs"]


async def test_greenhouse_adapter_returns_empty_on_404() -> None:
    company = _CompanyStub(careers_url="https://boards.greenhouse.io/acme")
    postings = await GreenhouseAdapter().list_postings(company, _StubFetcher("", status=404))
    assert postings == []


async def test_greenhouse_adapter_returns_empty_on_garbage_feed() -> None:
    company = _CompanyStub(careers_url="https://boards.greenhouse.io/acme")
    postings = await GreenhouseAdapter().list_postings(company, _StubFetcher("not json"))
    assert postings == []


async def test_greenhouse_adapter_returns_empty_without_a_derivable_token() -> None:
    company = _CompanyStub()
    fetcher = _StubFetcher((ATS_FIXTURES_DIR / "greenhouse" / "jobs.json").read_text())

    postings = await GreenhouseAdapter().list_postings(company, fetcher)

    assert postings == []
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


async def test_lever_adapter_returns_empty_on_404() -> None:
    company = _CompanyStub(careers_url="https://jobs.lever.co/acme")
    postings = await LeverAdapter().list_postings(company, _StubFetcher("", status=404))
    assert postings == []


async def test_lever_adapter_returns_empty_on_garbage_feed() -> None:
    company = _CompanyStub(careers_url="https://jobs.lever.co/acme")
    postings = await LeverAdapter().list_postings(company, _StubFetcher("<html>nope</html>"))
    assert postings == []


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


async def test_ashby_adapter_returns_empty_on_404() -> None:
    company = _CompanyStub(careers_url="https://jobs.ashbyhq.com/acme")
    postings = await AshbyAdapter().list_postings(company, _StubFetcher("", status=404))
    assert postings == []


async def test_ashby_adapter_returns_empty_on_garbage_feed() -> None:
    company = _CompanyStub(careers_url="https://jobs.ashbyhq.com/acme")
    postings = await AshbyAdapter().list_postings(company, _StubFetcher("{not valid"))
    assert postings == []


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


async def test_smartrecruiters_adapter_derives_token_from_domain_fallback() -> None:
    body = (ATS_FIXTURES_DIR / "smartrecruiters" / "postings.json").read_text()
    company = _CompanyStub(domain="deliveryhero.com")
    fetcher = _StubFetcher(body)

    postings = await SmartRecruitersAdapter().list_postings(company, fetcher)

    assert len(postings) == 3
    assert fetcher.calls == ["https://api.smartrecruiters.com/v1/companies/deliveryhero/postings"]


async def test_smartrecruiters_adapter_returns_empty_on_404() -> None:
    company = _CompanyStub(careers_url="https://jobs.smartrecruiters.com/DeliveryHero")
    postings = await SmartRecruitersAdapter().list_postings(company, _StubFetcher("", status=404))
    assert postings == []


async def test_smartrecruiters_adapter_returns_empty_on_garbage_feed() -> None:
    company = _CompanyStub(careers_url="https://jobs.smartrecruiters.com/DeliveryHero")
    postings = await SmartRecruitersAdapter().list_postings(company, _StubFetcher("not json"))
    assert postings == []


async def test_smartrecruiters_adapter_returns_empty_without_a_derivable_token() -> None:
    company = _CompanyStub()
    fetcher = _StubFetcher((ATS_FIXTURES_DIR / "smartrecruiters" / "postings.json").read_text())

    postings = await SmartRecruitersAdapter().list_postings(company, fetcher)

    assert postings == []
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


async def test_recruitee_adapter_returns_empty_on_404() -> None:
    company = _CompanyStub(careers_url="https://bunq.recruitee.com/")
    postings = await RecruiteeAdapter().list_postings(company, _StubFetcher("", status=404))
    assert postings == []


async def test_recruitee_adapter_returns_empty_on_garbage_feed() -> None:
    company = _CompanyStub(careers_url="https://bunq.recruitee.com/")
    postings = await RecruiteeAdapter().list_postings(company, _StubFetcher("not json"))
    assert postings == []


async def test_recruitee_adapter_returns_empty_without_a_derivable_token() -> None:
    company = _CompanyStub()
    fetcher = _StubFetcher((ATS_FIXTURES_DIR / "recruitee" / "offers.json").read_text())

    postings = await RecruiteeAdapter().list_postings(company, fetcher)

    assert postings == []
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


async def test_workable_adapter_derives_token_from_domain_fallback() -> None:
    body = (ATS_FIXTURES_DIR / "workable" / "widget.json").read_text()
    company = _CompanyStub(domain="mondu.com")
    fetcher = _StubFetcher(body)

    postings = await WorkableAdapter().list_postings(company, fetcher)

    assert len(postings) == 3
    assert fetcher.calls == ["https://apply.workable.com/api/v1/widget/accounts/mondu?details=true"]


async def test_workable_adapter_returns_empty_on_404() -> None:
    company = _CompanyStub(careers_url="https://apply.workable.com/mondu/")
    postings = await WorkableAdapter().list_postings(company, _StubFetcher("", status=404))
    assert postings == []


async def test_workable_adapter_returns_empty_on_garbage_feed() -> None:
    company = _CompanyStub(careers_url="https://apply.workable.com/mondu/")
    postings = await WorkableAdapter().list_postings(company, _StubFetcher("not json"))
    assert postings == []


async def test_workable_adapter_returns_empty_without_a_derivable_token() -> None:
    company = _CompanyStub()
    fetcher = _StubFetcher((ATS_FIXTURES_DIR / "workable" / "widget.json").read_text())

    postings = await WorkableAdapter().list_postings(company, fetcher)

    assert postings == []
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


async def test_personio_adapter_derives_token_from_domain_fallback() -> None:
    """The token lives in the subdomain (smava.jobs.personio.de), same family as Recruitee —
    falling back to the company's plain domain must still resolve the right feed URL."""
    body = (ATS_FIXTURES_DIR / "personio" / "jobs.xml").read_text()
    company = _CompanyStub(domain="smava.de")
    fetcher = _StubFetcher(body, content_type="text/xml")

    postings = await PersonioAdapter().list_postings(company, fetcher)

    assert len(postings) == 2
    assert fetcher.calls == ["https://smava.jobs.personio.de/xml"]


async def test_personio_adapter_returns_empty_on_404() -> None:
    company = _CompanyStub(careers_url="https://smava.jobs.personio.de/")
    postings = await PersonioAdapter().list_postings(company, _StubFetcher("", status=404))
    assert postings == []


async def test_personio_adapter_returns_empty_on_garbage_feed() -> None:
    company = _CompanyStub(careers_url="https://smava.jobs.personio.de/")
    postings = await PersonioAdapter().list_postings(
        company, _StubFetcher("not xml at all", content_type="text/xml")
    )
    assert postings == []


async def test_personio_adapter_returns_empty_without_a_derivable_token() -> None:
    company = _CompanyStub()
    fetcher = _StubFetcher((ATS_FIXTURES_DIR / "personio" / "jobs.xml").read_text())

    postings = await PersonioAdapter().list_postings(company, fetcher)

    assert postings == []
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


async def test_generic_html_adapter_returns_empty_on_fixture_miss() -> None:
    company = _CompanyStub(careers_url="https://unknown.example/careers")
    fetcher = RecordedFetcher(FIXTURES_DIR)

    postings = await GenericHtmlAdapter().list_postings(company, fetcher)

    assert postings == []


async def test_generic_html_adapter_returns_empty_without_careers_url() -> None:
    company = _CompanyStub()
    postings = await GenericHtmlAdapter().list_postings(company, RecordedFetcher(FIXTURES_DIR))
    assert postings == []
