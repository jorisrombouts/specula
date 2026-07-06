from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SkillDemand(CamelModel):
    skill: str
    pct: int
    delta: int
    up: bool
    gap: bool = False


class TrendSeries(CamelModel):
    name: str
    color: str
    data: list[int]


class Trend(CamelModel):
    weeks: list[str]
    series: list[TrendSeries]


class SeniorityMix(CamelModel):
    k: str
    v: int


class ModeMix(CamelModel):
    k: str
    v: int
    color: str


class SalaryBand(CamelModel):
    band: str
    lo: int
    hi: int


class ActiveCompany(CamelModel):
    name: str
    n: int


class Insights(CamelModel):
    period: str
    total_analysed: int
    low_conf_excluded: int
    skill_demand: list[SkillDemand]
    trend: Trend
    seniority_mix: list[SeniorityMix]
    mode_mix: list[ModeMix]
    salary: list[SalaryBand]
    active_companies: list[ActiveCompany]


class SkillsGap(CamelModel):
    skill: str
    roles: int
    note: str
