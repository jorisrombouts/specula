"""RecordingOpenAIClient + RecordingFetcher: wrap a live client, mirror results to fixtures.

Uses stub "live" clients (no network, no real OpenAI SDK) to assert the wrappers (a) delegate
to the wrapped live client and return its result unchanged, and (b) write a fixture file at the
exact path/shape `RecordedOpenAIClient`/`RecordedFetcher` read from — see test_openai_recorded.py
and test_http_politeness.py for the read-side key scheme this must match.
"""

import hashlib
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from specula_api.config import Settings
from specula_api.pipeline.deps import build_deps
from specula_api.pipeline.http import FetchedDoc, RecordedFetcher, RecordingFetcher
from specula_api.pipeline.openai_client import (
    EnrichResult,
    ExtractionResult,
    MeteringOpenAIClient,
    RecordedOpenAIClient,
    RecordingOpenAIClient,
    Source,
)


class _StubLiveFetcher:
    def __init__(self, doc: FetchedDoc) -> None:
        self._doc = doc
        self.closed = False

    async def get(self, url: str, *, accept: str = "text/html") -> FetchedDoc:
        return self._doc

    async def aclose(self) -> None:
        self.closed = True


class _StubLiveOpenAIClient:
    """Returns fixed results; records what it was called with for assertions."""

    def __init__(self) -> None:
        self.closed = False

    async def discover_sources(
        self, queries: Sequence[str], *, allowed_domains: Sequence[str] | None = None
    ) -> list[Source]:
        return [Source(url="https://boards.greenhouse.io/acme/jobs/1", title="Engineer")]

    async def enrich_company(
        self, *, name: str, domain: str | None, page_text: str | None
    ) -> EnrichResult:
        return EnrichResult(hq_country="US", hq_confidence=80, ats="greenhouse")

    async def extract_posting(
        self, *, page_text: str, company_name: str | None = None
    ) -> ExtractionResult:
        return ExtractionResult(
            title="Engineer",
            required_skills=["Python"],
            deadline_at=date(2026, 8, 15),
            extraction_confidence=90,
        )

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

    async def approval_whys(self, descriptions: Sequence[str]) -> list[str]:
        raise NotImplementedError

    async def rationale(
        self, *, factors: dict[str, int], overlap: tuple[int, int], red_flag: str | None
    ) -> str:
        return "Strong match."

    async def aclose(self) -> None:
        self.closed = True


def _settings(**overrides: object) -> Settings:
    return Settings(**overrides)  # type: ignore[arg-type]


# --- RecordingFetcher -----------------------------------------------------------


async def test_recording_fetcher_delegates_and_returns_live_result(tmp_path: Path) -> None:
    doc = FetchedDoc(url="https://acme.example/careers", status=200, text="hi")
    live = _StubLiveFetcher(doc)
    fetcher = RecordingFetcher(live, tmp_path)

    result = await fetcher.get("https://acme.example/careers")

    assert result == doc


async def test_recording_fetcher_writes_fixture_recorded_fetcher_can_read(tmp_path: Path) -> None:
    doc = FetchedDoc(
        url="https://acme.example/careers", status=200, text="hi", content_type="text/html"
    )
    live = _StubLiveFetcher(doc)
    fetcher = RecordingFetcher(live, tmp_path)

    await fetcher.get("https://acme.example/careers")

    key = hashlib.sha256(b"https://acme.example/careers").hexdigest()
    path = tmp_path / "http" / f"{key}.json"
    assert path.exists()
    assert json.loads(path.read_text()) == doc.model_dump()

    # And RecordedFetcher (the read side) resolves the exact same fixture.
    replayed = await RecordedFetcher(tmp_path).get("https://acme.example/careers")
    assert replayed == doc


async def test_recording_fetcher_aclose_closes_the_live_fetcher(tmp_path: Path) -> None:
    live = _StubLiveFetcher(FetchedDoc(url="https://acme.example", status=200, text=""))
    fetcher = RecordingFetcher(live, tmp_path)

    await fetcher.aclose()

    assert live.closed is True


# --- RecordingOpenAIClient -------------------------------------------------------


async def test_recording_openai_client_delegates_discover_sources(tmp_path: Path) -> None:
    client = RecordingOpenAIClient(_StubLiveOpenAIClient(), tmp_path)

    sources = await client.discover_sources(
        ["ml engineer berlin"], allowed_domains=["greenhouse.io"]
    )

    assert sources == [Source(url="https://boards.greenhouse.io/acme/jobs/1", title="Engineer")]


async def test_recording_openai_client_writes_fixtures_recorded_client_can_read(
    tmp_path: Path,
) -> None:
    client = RecordingOpenAIClient(_StubLiveOpenAIClient(), tmp_path)
    recorded = RecordedOpenAIClient(tmp_path)

    await client.discover_sources(["ml engineer berlin"], allowed_domains=["greenhouse.io"])
    replayed_sources = await recorded.discover_sources(
        ["ml engineer berlin"], allowed_domains=["greenhouse.io"]
    )
    assert replayed_sources == [
        Source(url="https://boards.greenhouse.io/acme/jobs/1", title="Engineer")
    ]

    await client.enrich_company(name="Acme", domain="acme.com", page_text=None)
    replayed_enrich = await recorded.enrich_company(name="Acme", domain="acme.com", page_text=None)
    assert replayed_enrich == EnrichResult(hq_country="US", hq_confidence=80, ats="greenhouse")

    await client.extract_posting(page_text="some job page")
    replayed_extract = await recorded.extract_posting(page_text="some job page")
    assert replayed_extract.title == "Engineer"
    assert replayed_extract.deadline_at == date(2026, 8, 15)

    await client.embed(["Python"])
    [replayed_vec] = await recorded.embed(["Python"])
    assert replayed_vec == [0.1, 0.2, 0.3]

    await client.rationale(factors={"role": 80}, overlap=(1, 2), red_flag=None)
    replayed_rationale = await recorded.rationale(
        factors={"role": 80}, overlap=(1, 2), red_flag=None
    )
    assert replayed_rationale == "Strong match."


async def test_recording_openai_client_aclose_closes_the_live_client(tmp_path: Path) -> None:
    live = _StubLiveOpenAIClient()
    client = RecordingOpenAIClient(live, tmp_path)

    await client.aclose()

    assert live.closed is True


# --- build_deps("record") wiring --------------------------------------------------


async def test_build_deps_record_mode_wires_recording_variants(tmp_path: Path) -> None:
    # AsyncOpenAI (openai 2.45) raises at construction time, not first call, if no api_key is
    # given (env or explicit) — a fake key is enough since this test never makes a network call.
    deps = build_deps(
        _settings(
            pipeline_mode="record", pipeline_fixtures_dir=str(tmp_path), openai_api_key="test-key"
        )
    )
    try:
        # build_deps now wraps the mode-selected client in cost metering (OBS lane); the
        # recording variant is the wrapped `inner`.
        assert isinstance(deps.openai, MeteringOpenAIClient)
        assert isinstance(deps.openai.inner, RecordingOpenAIClient)
        assert isinstance(deps.fetcher, RecordingFetcher)
    finally:
        await deps.aclose()
