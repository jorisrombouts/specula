from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from specula_api.schemas.run import RunOut


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class TokensByStage(CamelModel):
    stage: str
    total_tokens: int


class TokenPoint(CamelModel):
    date: str  # YYYY-MM-DD (frozen contract types this as a string)
    total_tokens: int
    runs: int


class DashboardSummary(CamelModel):
    total_tokens: int
    run_count: int
    tokens_by_stage: list[TokensByStage]
    tokens_by_day: list[TokenPoint]
    recent_runs: list[RunOut]
