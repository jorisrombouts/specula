"""DI seam: wires the pipeline's external dependencies (OpenAI, HTTP, clock) into one object."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from specula_api.config import Settings
from specula_api.pipeline.http import Fetcher, PoliteFetcher, RecordedFetcher, RecordingFetcher
from specula_api.pipeline.openai_client import (
    MeteringOpenAIClient,
    OpenAIClient,
    OpenAIResponsesClient,
    RecordedOpenAIClient,
    RecordingOpenAIClient,
    UsageSink,
)

# apps/api/tests/fixtures/pipeline — used for "recorded" mode when settings.pipeline_fixtures_dir
# is unset, so tests (and local dev) can build recorded deps without any env configuration.
DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "pipeline"


@dataclass(frozen=True)
class PipelineDeps:
    openai: OpenAIClient
    fetcher: Fetcher
    settings: Settings
    now: Callable[[], datetime]  # deterministic clock override for tests
    # Populated by build_deps; None for hand-built deps in unit/pipeline tests. When set,
    # services/run.py drains it into `llm_costs` rows (OBS).
    usage_sink: UsageSink | None = None

    async def aclose(self) -> None:
        await self.openai.aclose()
        await self.fetcher.aclose()


def build_live_deps(settings: Settings) -> PipelineDeps:
    return PipelineDeps(
        openai=OpenAIResponsesClient(settings),
        fetcher=PoliteFetcher(settings),
        settings=settings,
        now=lambda: datetime.now(tz=UTC),
    )


def build_recorded_deps(
    settings: Settings, fixtures_dir: Path, *, now: datetime | None = None
) -> PipelineDeps:
    frozen_now = now or datetime.now(tz=UTC)
    return PipelineDeps(
        openai=RecordedOpenAIClient(fixtures_dir),
        fetcher=RecordedFetcher(fixtures_dir),
        settings=settings,
        now=lambda: frozen_now,
    )


def build_record_deps(settings: Settings, fixtures_dir: Path) -> PipelineDeps:
    """Live clients wrapped to mirror each result into `fixtures_dir` — a live run that also
    regenerates the fixtures a "recorded" run/CI replays. See `RecordingOpenAIClient`/
    `RecordingFetcher`."""
    return PipelineDeps(
        openai=RecordingOpenAIClient(OpenAIResponsesClient(settings), fixtures_dir),
        fetcher=RecordingFetcher(PoliteFetcher(settings), fixtures_dir),
        settings=settings,
        now=lambda: datetime.now(tz=UTC),
    )


def _with_metering(deps: PipelineDeps, settings: Settings) -> PipelineDeps:
    """Wrap deps.openai in token metering feeding a fresh per-run UsageSink (OBS)."""
    sink = UsageSink()
    return replace(deps, openai=MeteringOpenAIClient(deps.openai, sink, settings), usage_sink=sink)


def build_deps(settings: Settings) -> PipelineDeps:
    fixtures_dir = Path(settings.pipeline_fixtures_dir or DEFAULT_FIXTURES_DIR)
    if settings.pipeline_mode == "recorded":
        base = build_recorded_deps(settings, fixtures_dir)
    elif settings.pipeline_mode == "record":
        base = build_record_deps(settings, fixtures_dir)
    else:
        base = build_live_deps(settings)
    return _with_metering(base, settings)
