"""DI seam: wires the pipeline's external dependencies (OpenAI, HTTP, clock) into one object."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from specula_api.config import Settings
from specula_api.pipeline.http import Fetcher, PoliteFetcher, RecordedFetcher
from specula_api.pipeline.openai_client import (
    OpenAIClient,
    OpenAIResponsesClient,
    RecordedOpenAIClient,
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


def build_deps(settings: Settings) -> PipelineDeps:
    if settings.pipeline_mode == "recorded":
        fixtures_dir = Path(settings.pipeline_fixtures_dir or DEFAULT_FIXTURES_DIR)
        return build_recorded_deps(settings, fixtures_dir)
    return build_live_deps(settings)
