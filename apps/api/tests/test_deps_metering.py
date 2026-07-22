"""build_deps must wire cost metering (OBS lane): a per-run CostSink and a MeteringOpenAIClient
wrapping whatever base client the pipeline mode selected. Hand-built PipelineDeps (used by the
pipeline tests) keep working because cost_sink defaults to None."""

from datetime import UTC, datetime
from pathlib import Path

from specula_api.config import Settings
from specula_api.pipeline.deps import DEFAULT_FIXTURES_DIR, PipelineDeps, build_deps
from specula_api.pipeline.http import RecordedFetcher
from specula_api.pipeline.openai_client import CostSink, MeteringOpenAIClient, RecordedOpenAIClient


def test_build_deps_recorded_wraps_openai_in_metering_with_a_sink() -> None:
    settings = Settings(pipeline_mode="recorded", pipeline_fixtures_dir=str(DEFAULT_FIXTURES_DIR))
    deps = build_deps(settings)
    assert isinstance(deps.openai, MeteringOpenAIClient)
    assert isinstance(deps.cost_sink, CostSink)
    assert deps.cost_sink.run_budget_usd == settings.openai_run_budget_usd
    assert deps.cost_sink.daily_budget_usd == settings.openai_daily_budget_usd


def test_hand_built_deps_default_to_no_cost_sink() -> None:
    deps = PipelineDeps(
        openai=RecordedOpenAIClient(Path(DEFAULT_FIXTURES_DIR)),
        fetcher=RecordedFetcher(Path(DEFAULT_FIXTURES_DIR)),
        settings=Settings(),
        now=lambda: datetime.now(UTC),
    )
    assert deps.cost_sink is None
