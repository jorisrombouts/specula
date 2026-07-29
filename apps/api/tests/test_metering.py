"""Unit tests for the OpenAI cost-metering seam (OBS lane): MeteringOpenAIClient + CostSink.
No DB, no network — a hand-built inner stub supplies outputs."""

from collections.abc import Sequence
from decimal import Decimal

from specula_api.config import OPENAI_PRICING, Settings
from specula_api.pipeline.openai_client import (
    CostRecord,
    CostSink,
    EnrichResult,
    ExtractionResult,
    MeteringOpenAIClient,
    Source,
    estimate_tokens,
)


class _StubOpenAI:
    """Minimal OpenAIClient returning fixed outputs; records call counts."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def discover_sources(
        self, queries: Sequence[str], *, allowed_domains: Sequence[str] | None = None
    ) -> list[Source]:
        self.calls.append("discover_sources")
        return [Source(url="https://boards.greenhouse.io/acme/jobs/1")]

    async def enrich_company(
        self, *, name: str, domain: str | None, page_text: str | None
    ) -> EnrichResult:
        self.calls.append("enrich_company")
        return EnrichResult(hq_country="DE")

    async def extract_posting(
        self, *, page_text: str, company_name: str | None = None
    ) -> ExtractionResult:
        self.calls.append("extract_posting")
        return ExtractionResult(title="Engineer", extraction_confidence=80)

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append("embed")
        return [[0.0] * 3 for _ in texts]

    async def rationale(
        self, *, factors: dict[str, int], overlap: tuple[int, int], red_flag: str | None
    ) -> str:
        self.calls.append("rationale")
        return "A solid match."

    async def approval_whys(self, descriptions: Sequence[str]) -> list[str]:
        self.calls.append("approval_whys")
        return ["worth a look" for _ in descriptions]

    async def aclose(self) -> None:
        self.calls.append("aclose")


def _pricing_cost(rec: CostRecord) -> Decimal:
    price = OPENAI_PRICING[rec.model]
    usd = (
        rec.prompt_tokens * price["prompt"]
        + rec.completion_tokens * price["completion"]
        + rec.embed_tokens * price["embed"]
    ) / 1_000_000
    return Decimal(str(usd)).quantize(Decimal("0.000001"))


def _metered() -> tuple[MeteringOpenAIClient, _StubOpenAI, CostSink]:
    settings = Settings()
    sink = CostSink()
    inner = _StubOpenAI()
    return MeteringOpenAIClient(inner, sink, settings), inner, sink


def test_estimate_tokens_is_deterministic_and_positive() -> None:
    assert estimate_tokens("hello world") == estimate_tokens("hello world")
    assert estimate_tokens("a" * 40) == 10
    assert estimate_tokens("") == 0
    assert estimate_tokens("x") >= 1


async def test_metering_delegates_and_returns_inner_result() -> None:
    metered, inner, _ = _metered()
    result = await metered.extract_posting(page_text="some page text here")
    assert result.title == "Engineer"
    assert inner.calls == ["extract_posting"]


async def test_each_call_records_one_row_with_stage_model_and_pricing_cost() -> None:
    metered, _, sink = _metered()
    settings = Settings()

    await metered.discover_sources(["ml engineer jobs"])
    await metered.enrich_company(name="Acme", domain="acme.com", page_text="about acme")
    await metered.extract_posting(page_text="a real posting body")
    await metered.embed(["python", "postgres"])
    await metered.rationale(factors={"role": 80, "skill": 70}, overlap=(2, 3), red_flag=None)
    await metered.approval_whys(["Acme; domain acme.com"])

    stages = [(r.stage, r.model) for r in sink.records]
    assert stages == [
        ("discovery", settings.openai_search_model),
        ("extract", settings.openai_extract_model),
        ("extract", settings.openai_extract_model),
        ("embed", settings.openai_embed_model),
        ("rationale", settings.openai_rationale_model),
        ("discovery", settings.openai_rationale_model),
    ]
    # every stored cost equals the OPENAI_PRICING formula applied to its token counts
    for rec in sink.records:
        assert rec.cost_usd == _pricing_cost(rec)


async def test_embed_row_bills_only_embed_tokens() -> None:
    metered, _, sink = _metered()
    await metered.embed(["python", "postgres"])
    [rec] = sink.records
    assert rec.embed_tokens > 0
    assert rec.prompt_tokens == 0
    assert rec.completion_tokens == 0


async def test_empty_embed_records_nothing() -> None:
    metered, _, sink = _metered()
    await metered.embed([])
    assert sink.records == []


def test_usage_sink_never_caps_regardless_of_volume() -> None:
    """The budget guard was removed (2026-07-29). A sink accumulates without limit."""
    sink = CostSink()
    for _ in range(50):
        sink.add(
            CostRecord(
                stage="rationale",
                model="gpt-4o",
                prompt_tokens=1_000_000,
                completion_tokens=1_000_000,
                embed_tokens=0,
                cost_usd=Decimal("12.50"),
            )
        )
    assert len(sink.records) == 50


def test_costsink_total_sums_records() -> None:
    sink = CostSink()
    sink.add(CostRecord("embed", "text-embedding-3-small", 0, 0, 10, Decimal("0.01")))
    sink.add(CostRecord("extract", "gpt-4o-mini", 100, 20, 0, Decimal("0.02")))
    assert sink.total == Decimal("0.03")
