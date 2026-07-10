"""RecordedOpenAIClient + build_recorded_deps: fixture-backed, no network, no DB."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from specula_api.config import Settings
from specula_api.pipeline.deps import DEFAULT_FIXTURES_DIR, build_recorded_deps
from specula_api.pipeline.http import RecordedFetcher
from specula_api.pipeline.openai_client import (
    EnrichResult,
    ExtractionResult,
    FixtureMissing,
    RecordedOpenAIClient,
    Source,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pipeline"

_DISCOVER_QUERIES = (
    "site:boards.greenhouse.io backend engineer remote",
    "software engineer jobs berlin",
)
_DISCOVER_DOMAINS = ("boards.greenhouse.io", "jobs.lever.co")

_EXTRACT_PAGE_TEXT = (
    "Senior Backend Engineer — Acme Corp\n\n"
    "We're hiring a Senior Backend Engineer to join our platform team in Berlin (hybrid). "
    "You'll design and operate distributed systems in Python and Go.\n\n"
    "Requirements: 5+ years backend experience, Python, PostgreSQL, distributed systems.\n"
    "Nice to have: Kubernetes, Kafka.\n"
    "Visa sponsorship available. Contract: full-time. Deadline: 2026-08-15.\n"
)

_RATIONALE_FACTORS = {"skills": 80, "seniority": 90, "location": 60}


def _client() -> RecordedOpenAIClient:
    return RecordedOpenAIClient(FIXTURES_DIR)


def _settings(**overrides: object) -> Settings:
    return Settings(**overrides)  # type: ignore[arg-type]


# --- discover_sources -------------------------------------------------------


async def test_discover_sources_parses_fixture() -> None:
    sources = await _client().discover_sources(_DISCOVER_QUERIES, allowed_domains=_DISCOVER_DOMAINS)

    assert len(sources) == 3
    assert sources[0] == Source(
        url="https://boards.greenhouse.io/acme/jobs/4123456",
        title="Senior Backend Engineer - Acme Corp",
    )
    assert all(isinstance(s, Source) for s in sources)


async def test_discover_sources_miss_raises_fixture_missing(tmp_path: Path) -> None:
    with pytest.raises(FixtureMissing, match=r"openai[/\\]discover"):
        await RecordedOpenAIClient(tmp_path).discover_sources(["never recorded"])


# --- enrich_company ----------------------------------------------------------


async def test_enrich_company_parses_fixture_keyed_by_domain() -> None:
    result = await _client().enrich_company(name="Acme Corp", domain="acme.com", page_text=None)

    assert result == EnrichResult(
        hq_country="US",
        hq_confidence=85,
        comp_estimate="$140k-$190k base, US market",
        careers_url="https://www.acmecorp.example/careers",
        ats="greenhouse",
    )


async def test_enrich_company_falls_back_to_name_when_domain_missing() -> None:
    # Same fixture, reached via the (slugified) `name` when `domain` is None.
    result = await _client().enrich_company(name="acme.com", domain=None, page_text=None)
    assert result.ats == "greenhouse"


async def test_enrich_company_miss_raises_fixture_missing(tmp_path: Path) -> None:
    with pytest.raises(FixtureMissing, match=r"openai[/\\]enrich"):
        await RecordedOpenAIClient(tmp_path).enrich_company(
            name="Nobody Corp", domain="nobody.example", page_text=None
        )


# --- extract_posting ----------------------------------------------------------


async def test_extract_posting_parses_fixture() -> None:
    result = await _client().extract_posting(page_text=_EXTRACT_PAGE_TEXT, company_name="Acme Corp")

    assert isinstance(result, ExtractionResult)
    assert result.title == "Senior Backend Engineer"
    assert result.required_skills == ["Python", "PostgreSQL", "Distributed Systems"]
    assert result.extraction_confidence == 82


async def test_extract_posting_miss_raises_fixture_missing(tmp_path: Path) -> None:
    with pytest.raises(FixtureMissing, match=r"openai[/\\]extract"):
        await RecordedOpenAIClient(tmp_path).extract_posting(page_text="never recorded")


# --- embed ---------------------------------------------------------------------


async def test_embed_miss_returns_deterministic_pseudo_vector(tmp_path: Path) -> None:
    client = RecordedOpenAIClient(tmp_path)

    first = await client.embed(["Python"])
    second = await client.embed(["Python"])

    assert len(first) == 1
    assert len(first[0]) == 1536
    assert first == second  # stable across calls (and across client instances)


async def test_embed_pseudo_vectors_differ_by_text(tmp_path: Path) -> None:
    [python_vec, rust_vec] = await RecordedOpenAIClient(tmp_path).embed(["Python", "Rust"])
    assert python_vec != rust_vec


async def test_embed_uses_fixture_when_present(tmp_path: Path) -> None:
    text = "Python"
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()
    embed_dir = tmp_path / "openai" / "embed"
    embed_dir.mkdir(parents=True)
    recorded_vector = [0.1] * 1536
    (embed_dir / f"{key}.json").write_text(json.dumps(recorded_vector))

    [vector] = await RecordedOpenAIClient(tmp_path).embed([text])

    assert vector == recorded_vector


# --- rationale -------------------------------------------------------------------


async def test_rationale_parses_fixture() -> None:
    text = await _client().rationale(factors=_RATIONALE_FACTORS, overlap=(3, 5), red_flag=None)
    assert text.startswith("Strong skills and seniority match")


async def test_rationale_miss_raises_fixture_missing(tmp_path: Path) -> None:
    with pytest.raises(FixtureMissing, match=r"openai[/\\]rationale"):
        await RecordedOpenAIClient(tmp_path).rationale(
            factors={"skills": 1}, overlap=(0, 1), red_flag=None
        )


# --- build_recorded_deps -----------------------------------------------------------


async def test_build_recorded_deps_wires_recorded_variants() -> None:
    frozen = datetime(2026, 1, 1, tzinfo=UTC)
    deps = build_recorded_deps(_settings(), FIXTURES_DIR, now=frozen)

    assert isinstance(deps.openai, RecordedOpenAIClient)
    assert isinstance(deps.fetcher, RecordedFetcher)
    assert deps.now() == frozen
    assert deps.now() == deps.now()  # frozen, not wall-clock


async def test_build_recorded_deps_defaults_now_to_a_frozen_clock() -> None:
    deps = build_recorded_deps(_settings(), FIXTURES_DIR)
    assert deps.now() == deps.now()


def test_default_fixtures_dir_resolves_to_tests_fixtures_pipeline() -> None:
    assert DEFAULT_FIXTURES_DIR == FIXTURES_DIR


async def test_pipeline_deps_aclose_closes_recorded_variants_without_error() -> None:
    deps = build_recorded_deps(_settings(), FIXTURES_DIR)
    await deps.aclose()
