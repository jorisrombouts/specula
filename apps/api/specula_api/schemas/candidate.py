from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CandidateIn(CamelModel):
    headline: str | None = None
    location: str | None = None
    work_mode: str | None = None
    visa: str | None = None
    years: int | None = None
    education: str | None = None
    languages: list[str] = []
    skills: list[str] = []
    projects: list[dict[str, str]] = []
    experience: list[dict[str, str]] = []


class CandidateOut(CandidateIn):
    model_config = ConfigDict(from_attributes=True)

    updated_at: datetime
