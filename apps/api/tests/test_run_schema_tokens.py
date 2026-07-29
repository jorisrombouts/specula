from datetime import UTC, datetime
from uuid import uuid4

from specula_api.db.models import Run
from specula_api.schemas.run import RunOut


def test_runout_serialises_tokens_camel() -> None:
    run = Run(
        id=uuid4(),
        kind="on_demand",
        status="done",
        started_at=None,
        finished_at=None,
        stats={"found": 0, "new": 0, "closed": 0, "low_conf_excluded": 0, "errors": 0},
        duration_ms=4200,
        created_at=datetime.now(UTC),
    )
    dumped = RunOut.from_model(run, total_tokens=1234).model_dump(by_alias=True)
    assert dumped["tokens"]["totalTokens"] == 1234
    assert dumped["durationMs"] == 4200


def test_runout_keeps_duration_when_no_tokens_were_recorded() -> None:
    """How long a run took is independent of whether it spent any tokens.

    A refresh run keys its ledger rows to the company (no Run exists for an ingest), so it
    has no rows of its own — `tokens` is rightly null, but its duration must still survive.
    """
    run = Run(
        id=uuid4(),
        kind="refresh",
        status="done",
        started_at=None,
        finished_at=None,
        stats={"found": 0, "new": 0, "closed": 0, "low_conf_excluded": 0, "errors": 0},
        duration_ms=8700,
        created_at=datetime.now(UTC),
    )
    dumped = RunOut.from_model(run).model_dump(by_alias=True)
    assert dumped["tokens"] is None
    assert dumped["durationMs"] == 8700
