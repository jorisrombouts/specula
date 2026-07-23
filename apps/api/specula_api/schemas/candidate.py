from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ⚠ Enum source of truth is packages/shared-types/src/index.ts
# (WORK_MODES / VISA_OPTIONS / CEFR_LEVELS). Keep these Literals in sync.
Mode = Literal["Remote", "Hybrid", "On-site"]
Visa = Literal[
    "EU/EEA/Swiss citizen — no sponsorship",
    "Have EU work/residence permit — no sponsorship",
    "Require visa sponsorship",
    "Require relocation + sponsorship",
]
CefrLevel = Literal["Native", "C2", "C1", "B2", "B1", "A2", "A1"]
Year = Annotated[int, Field(ge=1950, le=2100)]


class LanguageEntry(CamelModel):
    language: str
    level: CefrLevel


class EducationEntry(CamelModel):
    degree: str = ""
    field: str = ""
    institution: str = ""
    year: Year | None = None


class ProjectEntry(CamelModel):
    name: str = ""
    note: str = ""


class ExperienceEntry(CamelModel):
    role: str = ""
    org: str = ""
    start_year: Year | None = None
    end_year: Year | None = None


class CandidateIn(CamelModel):
    headline: str | None = None
    location: str | None = None
    work_mode: list[Mode] = []
    visa: Visa | None = None
    years: int | None = None
    education: list[EducationEntry] = []
    languages: list[LanguageEntry] = []
    skills: list[str] = []
    projects: list[ProjectEntry] = []
    experience: list[ExperienceEntry] = []


class CandidateOut(CandidateIn):
    model_config = ConfigDict(from_attributes=True)

    updated_at: datetime
