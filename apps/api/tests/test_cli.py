"""Selection logic for the live harness (`specula_api.cli`).

`prove-live` used to grab the oldest undecided ATS-flagged approval and report success even
when it ingested nothing: the board adapters derive their endpoint from an ATS-HOST domain
(or careers_url), so a seeded approval carrying the company's OWN domain (lighthouse.app,
tractable.ai) resolves to no board and yields 0 postings, silently.
"""

from uuid import uuid4

from specula_api.cli import first_ingestable
from specula_api.db.models import Approval


def _approval(domain: str, ats: str | None = "greenhouse") -> Approval:
    return Approval(user_id=uuid4(), name="X", domain=domain, ats=ats)


def test_skips_approval_whose_domain_is_the_companys_own() -> None:
    # `ats` is a stored hint and says greenhouse, but no board token can be derived from
    # lighthouse.app — the hint must NOT be trusted for this decision.
    assert first_ingestable([_approval("lighthouse.app")]) is None


def test_picks_the_first_ats_host_domain_skipping_unusable_ones() -> None:
    seeded = _approval("lighthouse.app")
    real = _approval("scopely.job-boards.greenhouse.io")

    assert first_ingestable([seeded, real]) is real


def test_recognises_every_supported_ats_host() -> None:
    hosts = [
        "acme.job-boards.greenhouse.io",
        "acme.jobs.eu.lever.co",
        "acme.jobs.ashbyhq.com",
        "careers.smartrecruiters.com",
        "acme.recruitee.com",
        "apply.workable.com",
        "acme.jobs.personio.de",
    ]
    for host in hosts:
        assert first_ingestable([_approval(host, ats=None)]) is not None, host


def test_returns_none_for_an_empty_queue() -> None:
    assert first_ingestable([]) is None
