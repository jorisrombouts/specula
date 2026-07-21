from pathlib import Path

import pytest
from pydantic import ValidationError

from specula_api.config import Settings

# A present-but-empty PIPELINE_MODE/PIPELINE_EXECUTION (e.g. `PIPELINE_MODE=` in a .env) used
# to fail Literal validation and crash every entrypoint that builds Settings (seed, CLI,
# uvicorn) — see config.py's `_blank_means_default`. Blank now means "not set", falling back
# to the field default; a genuinely invalid (non-blank) value must still raise.


def test_blank_pipeline_mode_kwarg_falls_back_to_default() -> None:
    assert Settings(pipeline_mode="").pipeline_mode == "live"  # type: ignore[arg-type]


def test_blank_pipeline_execution_kwarg_falls_back_to_default() -> None:
    assert Settings(pipeline_execution="   ").pipeline_execution == "inline"  # type: ignore[arg-type]


def test_blank_pipeline_mode_env_var_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The exact real-world scenario the fix addresses: a sourced `.env` with `PIPELINE_MODE=`
    # present but empty, not merely absent.
    monkeypatch.setenv("PIPELINE_MODE", "")
    monkeypatch.setenv("PIPELINE_EXECUTION", "")

    settings = Settings()

    assert settings.pipeline_mode == "live"
    assert settings.pipeline_execution == "inline"


def test_non_blank_pipeline_mode_is_respected_not_overridden() -> None:
    assert Settings(pipeline_mode="recorded").pipeline_mode == "recorded"


def test_invalid_non_blank_pipeline_mode_still_raises() -> None:
    # The blank-means-default carve-out must not swallow genuinely bad values.
    with pytest.raises(ValidationError):
        Settings(pipeline_mode="bogus")  # type: ignore[arg-type]


def test_env_file_includes_the_repo_root_absolutely_not_just_cwd_relative() -> None:
    """`.env` lives at the repo root, but every `just` recipe runs from `apps/api`, so a
    CWD-relative ".env" resolves to a file that doesn't exist — OPENAI_API_KEY silently loads
    as "" and the live CLI dies on its key check even though the key IS configured."""
    configured = Settings.model_config.get("env_file")
    entries = configured if isinstance(configured, (list, tuple)) else [configured]
    paths = [Path(str(entry)) for entry in entries if entry is not None]
    repo_root = Path(__file__).resolve().parents[3]

    assert any(p.is_absolute() and p == repo_root / ".env" for p in paths), paths
