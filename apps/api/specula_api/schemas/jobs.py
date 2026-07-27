from datetime import datetime

from pydantic import ConfigDict

from specula_api.schemas.targeting import CamelModel


class Factors(CamelModel):
    role: int
    skill: int
    loc: int


class JobOut(CamelModel):
    """Matches the `Job` interface in packages/shared-types/src/index.ts. `match`,
    `factors.loc`, `deadlineDays`, `posted`, `isNew` and `originVerified` are all
    DERIVED at read time — never read straight from a stored column."""

    id: str
    company: str
    logo: str
    title: str
    city: str
    country: str
    hq: str
    mode: str
    flag: str
    match: int
    factors: Factors
    overlap: tuple[int, int]
    seniority: str
    edu: str
    deadline_days: int
    salary: str | None
    posted: str
    status: str | None
    is_new: bool
    still_open: bool
    origin_verified: bool
    hq_conf: int
    red_flag: str | None = None
    stack: list[str]
    nice_to_have: list[str]
    visa: str
    langs: list[str]
    contract: str
    geo: str
    confidence: int
    dismiss_reason: str | None = None
    responsibilities: list[str]
    summary: str
    rationale: str
    source_url: str


class LensSummaryOut(CamelModel):
    """Matches `LensSummary`. `count` and `isNew` are DERIVED per lens at read time."""

    id: str
    name: str
    short: str
    active: bool
    scope: str
    modes: list[str]
    origin: str
    focus: str
    seeds: list[str]
    count: int
    is_new: int


class JobsResponseOut(CamelModel):
    jobs: list[JobOut]
    lenses: list[LensSummaryOut]
    sort: str


class JobStateIn(CamelModel):
    status: str | None = None
    note: str | None = None
    dismiss_reason: str | None = None
    feedback: str | None = None


class JobStateOut(CamelModel):
    model_config = ConfigDict(from_attributes=True)

    status: str | None
    note: str | None
    dismiss_reason: str | None
    feedback: str | None
    updated_at: datetime
