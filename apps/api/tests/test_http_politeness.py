import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import respx

from specula_api.config import Settings
from specula_api.pipeline.http import (
    MAX_RETRY_AFTER_S,
    BlockedTarget,
    Disallowed,
    PoliteFetcher,
    RecordedFetcher,
)


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "crawl_user_agent": "SpeculaBot/1.0 (+test)",
        "crawl_per_domain_delay_ms": 1000,
        "crawl_timeout_s": 5.0,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.fixture
def no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Replace asyncio.sleep with a recorder so backoff/throttle never actually blocks.

    Keeps the timing tests deterministic: we assert on the *recorded* sleep durations
    (the code path was exercised) instead of measuring wall-clock elapsed time.
    """
    recorded: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        recorded.append(delay)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)
    return recorded


@pytest.fixture
async def fetcher(no_real_sleep: list[float]) -> AsyncIterator[PoliteFetcher]:
    f = PoliteFetcher(_settings())
    try:
        yield f
    finally:
        await f.aclose()


async def test_robots_disallow_raises(fetcher: PoliteFetcher) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get("https://acme.example/robots.txt").respond(
            200, text="User-agent: *\nDisallow: /private"
        )
        with pytest.raises(Disallowed):
            await fetcher.get("https://acme.example/private/job-1")


async def test_robots_allow_permits_fetch(fetcher: PoliteFetcher) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get("https://acme.example/robots.txt").respond(
            200, text="User-agent: *\nDisallow: /private"
        )
        router.get("https://acme.example/careers").respond(200, text="<html>ok</html>")

        doc = await fetcher.get("https://acme.example/careers")

    assert doc.status == 200
    assert doc.text == "<html>ok</html>"


async def test_robots_fetch_failure_fails_open(fetcher: PoliteFetcher) -> None:
    with respx.mock(assert_all_called=False) as router:
        # robots.txt itself errors → we allow rather than block.
        router.get("https://acme.example/robots.txt").mock(side_effect=httpx.ConnectError("boom"))
        router.get("https://acme.example/jobs").respond(200, text="ok")

        doc = await fetcher.get("https://acme.example/jobs")

    assert doc.status == 200


async def test_get_returns_zero_status_doc_on_transport_error(fetcher: PoliteFetcher) -> None:
    """A dead host/DNS failure/connection reset must not crash a crawl — `get` returns a
    synthetic non-200 doc instead of propagating the httpx exception, so downstream stages
    (which already treat non-200 as "no page") skip the URL and move on."""
    with respx.mock(assert_all_called=False) as router:
        router.get("https://acme.example/robots.txt").respond(404)
        router.get("https://acme.example/jobs").mock(side_effect=httpx.ConnectError("boom"))

        doc = await fetcher.get("https://acme.example/jobs")

    assert doc.status == 0
    assert doc.text == ""
    assert doc.url == "https://acme.example/jobs"


async def test_429_then_200_is_retried(fetcher: PoliteFetcher, no_real_sleep: list[float]) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get("https://acme.example/robots.txt").respond(404)
        route = router.get("https://acme.example/jobs")
        route.side_effect = [
            httpx.Response(429, headers={"Retry-After": "2"}, text="slow down"),
            httpx.Response(200, text="ok"),
        ]

        doc = await fetcher.get("https://acme.example/jobs")

        assert route.call_count == 2

    assert doc.status == 200
    assert doc.text == "ok"
    # Retry-After was honored (2s) via the recorded backoff sleep, not a real wall-clock wait.
    assert 2.0 in no_real_sleep


async def test_retry_caps_at_three_attempts(
    fetcher: PoliteFetcher, no_real_sleep: list[float]
) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get("https://acme.example/robots.txt").respond(404)
        route = router.get("https://acme.example/jobs").respond(503)

        doc = await fetcher.get("https://acme.example/jobs")

        assert route.call_count == 3

    assert doc.status == 503


async def test_per_domain_delay_enforced_between_same_host_gets(
    fetcher: PoliteFetcher, no_real_sleep: list[float]
) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get("https://acme.example/robots.txt").respond(404)
        router.get(url__startswith="https://acme.example/jobs").respond(200, text="ok")

        await fetcher.get("https://acme.example/jobs/1")
        # First hit records the timestamp but doesn't sleep.
        assert no_real_sleep == []

        await fetcher.get("https://acme.example/jobs/2")

    # Second hit to the same host honors the 1000ms delay via the throttle path.
    assert len(no_real_sleep) == 1
    assert no_real_sleep[0] == pytest.approx(1.0, abs=0.05)


async def test_no_delay_across_different_hosts(
    fetcher: PoliteFetcher, no_real_sleep: list[float]
) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get("https://acme.example/robots.txt").respond(404)
        router.get("https://other.example/robots.txt").respond(404)
        router.get("https://acme.example/jobs").respond(200, text="ok")
        router.get("https://other.example/jobs").respond(200, text="ok")

        await fetcher.get("https://acme.example/jobs")
        await fetcher.get("https://other.example/jobs")

    # Different hosts have independent throttle clocks → no delay incurred.
    assert no_real_sleep == []


async def test_recorded_fetcher_miss_returns_404(tmp_path: Path) -> None:
    fetcher = RecordedFetcher(tmp_path)
    doc = await fetcher.get("https://acme.example/never-recorded")
    assert doc.status == 404
    assert doc.text == ""
    assert doc.url == "https://acme.example/never-recorded"
    await fetcher.aclose()


# --- SSRF guard ----------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # cloud instance metadata
        "http://127.0.0.1:8000/admin",
        "http://10.0.0.5/internal",
        "http://192.168.1.1/",
        "http://[::1]/x",
        "http://localhost:5432/",
        "http://db.internal/",
        "file:///etc/passwd",
        "mailto:careers@acme.example",
        "javascript:alert(1)",
    ],
)
async def test_non_public_targets_are_refused(fetcher: PoliteFetcher, url: str) -> None:
    """A posting's source_url comes from third-party ATS JSON or a scraped href — untrusted
    input that is later re-fetched, so it must not be able to reach loopback/link-local/
    private targets or non-http schemes."""
    with pytest.raises(BlockedTarget):
        await fetcher.get(url)


async def test_blocked_target_is_a_disallowed_so_adapters_already_handle_it(
    fetcher: PoliteFetcher,
) -> None:
    # Adapters translate Disallowed into BoardUnavailable; a blocked target must ride the
    # same path rather than mass-closing the company's postings.
    assert issubclass(BlockedTarget, Disallowed)


async def test_public_host_is_still_fetched(fetcher: PoliteFetcher) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get("https://acme.example/robots.txt").respond(404)
        router.get("https://acme.example/jobs").respond(200, text="ok")

        doc = await fetcher.get("https://acme.example/jobs")

    assert doc.status == 200


async def test_redirect_onto_a_blocked_target_is_refused(fetcher: PoliteFetcher) -> None:
    """robots + the guard are checked on the requested URL; a redirect must not be able to
    launder the fetch onto a private address."""
    with respx.mock(assert_all_called=False) as router:
        router.get("https://acme.example/robots.txt").respond(404)
        router.get("https://acme.example/jobs").respond(
            302, headers={"Location": "http://169.254.169.254/latest/meta-data/"}
        )
        router.get("http://169.254.169.254/latest/meta-data/").respond(200, text="secrets")

        with pytest.raises(BlockedTarget):
            await fetcher.get("https://acme.example/jobs")


# --- Retry-After bound ---------------------------------------------------------


async def test_absurd_retry_after_is_not_slept_off(
    fetcher: PoliteFetcher, no_real_sleep: list[float]
) -> None:
    """`Retry-After: 86400` must not park the run for a day. This executes inside a FastAPI
    BackgroundTask holding an open tenant_session, so an unbounded sleep pins a DB connection.
    We give up and surface the 429 (which adapters turn into BoardUnavailable) instead."""
    with respx.mock(assert_all_called=False) as router:
        router.get("https://acme.example/robots.txt").respond(404)
        route = router.get("https://acme.example/jobs").respond(
            429, headers={"Retry-After": "86400"}
        )

        doc = await fetcher.get("https://acme.example/jobs")

        assert route.call_count == 1  # gave up rather than waiting it out

    assert doc.status == 429
    assert all(delay <= MAX_RETRY_AFTER_S for delay in no_real_sleep), no_real_sleep


async def test_reasonable_retry_after_is_still_honoured(
    fetcher: PoliteFetcher, no_real_sleep: list[float]
) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get("https://acme.example/robots.txt").respond(404)
        route = router.get("https://acme.example/jobs")
        route.side_effect = [
            httpx.Response(429, headers={"Retry-After": "2"}, text="slow down"),
            httpx.Response(200, text="ok"),
        ]

        doc = await fetcher.get("https://acme.example/jobs")

    assert doc.status == 200
    assert 2.0 in no_real_sleep
