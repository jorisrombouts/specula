from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from specula_api.db.models import Approval

# Spec §6.1: HQ origin below this stored confidence is "surfaced, not trusted".
_HQ_CONFIDENCE_THRESHOLD = 75


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def _flag(country: str | None) -> str:
    """ISO-3166 alpha-2 → regional-indicator flag emoji ("NL" → 🇳🇱)."""
    if country is None or len(country) != 2 or not country.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in country.upper())


class ApprovalOut(CamelModel):
    id: UUID
    name: str | None
    logo: str | None
    domain: str | None
    ats: str | None
    hq: str | None
    flag: str
    query: str | None
    why: str | None
    careers_url: str | None
    roles: int
    unverified: bool

    @classmethod
    def from_model(cls, a: Approval) -> "ApprovalOut":
        return cls(
            id=a.id,
            name=a.name,
            logo=a.logo_url,
            domain=a.domain,
            ats=a.ats,
            hq=a.hq_country,
            flag=_flag(a.hq_country),
            query=a.found_query,
            why=a.why,
            careers_url=a.careers_url,
            roles=a.open_roles or 0,
            unverified=a.hq_confidence is None or a.hq_confidence < _HQ_CONFIDENCE_THRESHOLD,
        )


class DecisionIn(CamelModel):
    decision: Literal["approve", "reject", "snooze"]
