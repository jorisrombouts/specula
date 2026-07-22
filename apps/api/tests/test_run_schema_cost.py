from datetime import UTC, datetime
from uuid import uuid4

from specula_api.schemas.run import RunCost, RunOut, RunStats


def test_runout_serialises_cost_camel() -> None:
    out = RunOut(
        id=uuid4(),
        kind="on_demand",
        status="done",
        started_at=None,
        finished_at=None,
        stats=RunStats.model_validate(
            {"found": 0, "new": 0, "closed": 0, "low_conf_excluded": 0, "errors": 0}
        ),
        created_at=datetime.now(UTC),
        cost=RunCost(cost_usd=1.25, duration_ms=4200),
    )
    dumped = out.model_dump(by_alias=True)
    assert dumped["cost"]["costUsd"] == 1.25
    assert dumped["cost"]["durationMs"] == 4200
