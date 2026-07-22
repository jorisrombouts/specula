from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from specula_api.schemas.run import RunOut


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CostByStage(CamelModel):
    stage: str
    cost_usd: float


class CostPoint(CamelModel):
    date: str  # YYYY-MM-DD (frozen contract types this as a string)
    cost_usd: float
    runs: int


class DashboardSummary(CamelModel):
    total_cost_usd: float
    run_count: int
    cost_by_stage: list[CostByStage]
    cost_by_day: list[CostPoint]
    recent_runs: list[RunOut]
