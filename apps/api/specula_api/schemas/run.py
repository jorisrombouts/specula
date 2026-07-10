from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from specula_api.db.models import Run


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class RunStats(CamelModel):
    found: int = 0
    new: int = 0
    closed: int = 0
    low_conf_excluded: int = 0
    errors: int = 0


class RunOut(CamelModel):
    id: UUID
    kind: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    stats: RunStats
    created_at: datetime

    @classmethod
    def from_model(cls, run: Run) -> "RunOut":
        return cls(
            id=run.id,
            kind=run.kind,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            stats=RunStats.model_validate(run.stats),
            created_at=run.created_at,
        )
