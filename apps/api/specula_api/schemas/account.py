"""Schemas for GDPR data export. Serialize to the frozen `ExportBundle` camelCase shape
(packages/shared-types). The bundle's per-table arrays are typed `unknown[]` in TS — DATA
owns the row shapes — so these models are the authoritative definition of each row. Embedding
vectors (`*_vec`, 1536 floats) are excluded by omission: bulky and meaningless outside scoring.
`llm_costs` mirrors the frozen `LlmCost` interface exactly."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class CandidateExport(CamelModel):
    headline: str | None
    location: str | None
    work_mode: list[str]
    visa: str | None
    years: int | None
    education: list[Any]
    languages: list[Any]
    skills: list[str]
    projects: list[Any]
    experience: list[Any]
    updated_at: datetime


class TargetingExport(CamelModel):
    role_titles: list[str]
    seniority: list[str]
    must_haves: list[str]
    avoid: list[str]
    preferences: str | None
    updated_at: datetime


class CompanyExport(CamelModel):
    id: UUID
    name: str
    domain: str | None
    logo_url: str | None
    ats: str | None
    careers_url: str | None
    hq_country: str | None
    hq_confidence: int | None
    comp_estimate: str | None
    tracking: bool
    opt_out: bool
    status: str
    added_at: datetime


class PostingExport(CamelModel):
    id: UUID
    company_id: UUID | None
    source: str
    source_url: str
    content_hash: str
    title: str | None
    role_family: str | None
    city: str | None
    country: str | None
    hq_country: str | None
    work_mode: str | None
    seniority: str | None
    education: str | None
    required_skills: list[str]
    nice_to_have: list[str]
    visa: str | None
    languages: list[str]
    contract: str | None
    geo: str | None
    salary_text: str | None
    deadline_at: date | None
    posted_at: date | None
    responsibilities: list[str]
    summary: str | None
    still_open: bool | None
    extraction_confidence: int | None
    first_seen_at: datetime
    last_seen_at: datetime
    dedup_group: UUID | None


class ScoreExport(CamelModel):
    posting_id: UUID
    factor_role: int
    factor_skill: int
    overlap_matched: int
    overlap_total: int
    red_flag: str | None
    rationale: str
    scored_with: str
    scored_at: datetime


class LensExport(CamelModel):
    id: UUID
    name: str
    short: str | None
    scope: str | None
    modes: list[str]
    origin_rule: str | None
    focus: str | None
    seeds: list[str]
    active: bool
    is_default: bool
    created_at: datetime


class RunExport(CamelModel):
    id: UUID
    kind: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    stats: dict[str, Any]
    duration_ms: int | None
    created_at: datetime


class LlmCostExport(CamelModel):
    """Serializes to the frozen `LlmCost` interface — token counts only."""

    id: UUID
    run_id: UUID | None
    company_id: UUID | None
    stage: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    embed_tokens: int
    created_at: datetime


class ExportBundle(CamelModel):
    exported_at: datetime
    candidate: CandidateExport | None
    targeting: TargetingExport | None
    companies: list[CompanyExport]
    postings: list[PostingExport]
    scores: list[ScoreExport]
    lenses: list[LensExport]
    runs: list[RunExport]
    llm_costs: list[LlmCostExport]
