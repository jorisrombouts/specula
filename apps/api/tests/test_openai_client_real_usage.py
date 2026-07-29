"""OBS lane: `OpenAIResponsesClient` must surface OpenAI's real `.usage` on a side channel
(`last_usage`) so `MeteringOpenAIClient` records actual billed tokens instead of the
~4-chars/token estimate. Recorded/replay clients (`RecordedOpenAIClient`) have no such channel,
so metering keeps falling back to the estimate for them — this is what keeps the recorded-fixture
cost tests in test_metering.py/test_run_cost.py deterministic.

No real OpenAI network calls: `OpenAIResponsesClient._client`'s SDK methods are monkeypatched
with fakes exposing only the `.usage`/`.choices`/`.data` shape the client code reads.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from specula_api.config import Settings
from specula_api.pipeline.openai_client import (
    ExtractionResult,
    MeteringOpenAIClient,
    OpenAIResponsesClient,
    RealUsage,
    RecordedOpenAIClient,
    RecordingOpenAIClient,
    UsageSink,
    estimate_tokens,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pipeline"


@dataclass
class _FakeCompletionUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int = 0


@dataclass
class _FakeMessage:
    parsed: Any


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeCompletion:
    usage: _FakeCompletionUsage | None
    choices: list[_FakeChoice]


@dataclass
class _FakeResponseUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int = 0


@dataclass
class _FakeResponse:
    usage: _FakeResponseUsage | None
    output: list[object]


@dataclass
class _FakeEmbeddingUsage:
    prompt_tokens: int
    total_tokens: int = 0


@dataclass
class _FakeEmbeddingItem:
    embedding: list[float]


@dataclass
class _FakeEmbeddingResponse:
    data: list[_FakeEmbeddingItem]
    usage: _FakeEmbeddingUsage


def _live_client() -> OpenAIResponsesClient:
    return OpenAIResponsesClient(Settings(openai_api_key="test-key"))


async def test_extract_posting_captures_real_usage_from_dot_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _live_client()
    parsed = ExtractionResult(title="Engineer", extraction_confidence=80)
    completion = _FakeCompletion(
        usage=_FakeCompletionUsage(prompt_tokens=1234, completion_tokens=567),
        choices=[_FakeChoice(message=_FakeMessage(parsed=parsed))],
    )

    async def fake_parse(**_: object) -> _FakeCompletion:
        return completion

    monkeypatch.setattr(client._client.chat.completions, "parse", fake_parse)

    result = await client.extract_posting(page_text="short page")

    assert result is parsed
    assert client.last_usage == RealUsage(prompt_tokens=1234, completion_tokens=567)


async def test_metering_records_real_usage_not_the_char_estimate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _live_client()
    parsed = ExtractionResult(title="Engineer", extraction_confidence=80)
    completion = _FakeCompletion(
        usage=_FakeCompletionUsage(prompt_tokens=1234, completion_tokens=567),
        choices=[_FakeChoice(message=_FakeMessage(parsed=parsed))],
    )

    async def fake_parse(**_: object) -> _FakeCompletion:
        return completion

    monkeypatch.setattr(client._client.chat.completions, "parse", fake_parse)

    settings = Settings(openai_api_key="test-key")
    sink = UsageSink()
    metered = MeteringOpenAIClient(client, sink, settings)

    page_text = "short page"  # ~4-chars/token estimate would be tiny, nowhere near 1234/567
    await metered.extract_posting(page_text=page_text)

    [rec] = sink.records
    assert rec.prompt_tokens == 1234
    assert rec.completion_tokens == 567
    assert rec.prompt_tokens != estimate_tokens(page_text, "")


async def test_embed_captures_real_usage_as_embed_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _live_client()
    response = _FakeEmbeddingResponse(
        data=[_FakeEmbeddingItem(embedding=[0.1, 0.2])],
        usage=_FakeEmbeddingUsage(prompt_tokens=999),
    )

    async def fake_create(**_: object) -> _FakeEmbeddingResponse:
        return response

    monkeypatch.setattr(client._client.embeddings, "create", fake_create)

    vectors = await client.embed(["hello"])

    assert vectors == [[0.1, 0.2]]
    assert client.last_usage == RealUsage(embed_tokens=999)


async def test_discover_sources_accumulates_real_usage_across_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _live_client()
    usages = iter(
        [
            _FakeResponseUsage(input_tokens=100, output_tokens=10),
            _FakeResponseUsage(input_tokens=50, output_tokens=5),
        ]
    )

    async def fake_create(**_: object) -> _FakeResponse:
        return _FakeResponse(usage=next(usages), output=[])

    monkeypatch.setattr(client._client.responses, "create", fake_create)

    await client.discover_sources(["query one", "query two"])

    assert client.last_usage == RealUsage(prompt_tokens=150, completion_tokens=15)


async def test_missing_dot_usage_falls_back_to_estimate(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _live_client()
    parsed = ExtractionResult(title="Engineer", extraction_confidence=80)
    completion = _FakeCompletion(
        usage=None, choices=[_FakeChoice(message=_FakeMessage(parsed=parsed))]
    )

    async def fake_parse(**_: object) -> _FakeCompletion:
        return completion

    monkeypatch.setattr(client._client.chat.completions, "parse", fake_parse)

    settings = Settings(openai_api_key="test-key")
    sink = UsageSink()
    metered = MeteringOpenAIClient(client, sink, settings)

    page_text = "short page"
    await metered.extract_posting(page_text=page_text)

    assert client.last_usage is None
    [rec] = sink.records
    assert rec.prompt_tokens == estimate_tokens(page_text, "")
    assert rec.completion_tokens == estimate_tokens(parsed.model_dump_json())


async def test_recorded_client_has_no_usage_channel_so_metering_estimates() -> None:
    settings = Settings()
    sink = UsageSink()
    recorded = RecordedOpenAIClient(FIXTURES_DIR)
    metered = MeteringOpenAIClient(recorded, sink, settings)

    vectors = await metered.embed(["python"])

    assert vectors  # deterministic pseudo-vector fallback, no fixture needed
    [rec] = sink.records
    assert rec.embed_tokens == estimate_tokens("python")


async def test_recording_client_proxies_real_usage_from_wrapped_live_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _live_client()
    parsed = ExtractionResult(title="Engineer", extraction_confidence=80)
    completion = _FakeCompletion(
        usage=_FakeCompletionUsage(prompt_tokens=42, completion_tokens=7),
        choices=[_FakeChoice(message=_FakeMessage(parsed=parsed))],
    )

    async def fake_parse(**_: object) -> _FakeCompletion:
        return completion

    monkeypatch.setattr(client._client.chat.completions, "parse", fake_parse)

    recording = RecordingOpenAIClient(client, tmp_path)
    await recording.extract_posting(page_text="short page")

    assert recording.last_usage == RealUsage(prompt_tokens=42, completion_tokens=7)
