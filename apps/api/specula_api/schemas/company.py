from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from specula_api.db.models import Company


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def _flag(country_code: str | None) -> str:
    """Derive a flag emoji from a 2-letter ISO country code (e.g. FR → 🇫🇷)."""
    if not country_code or len(country_code) != 2 or not country_code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in country_code.upper())


class CompanyOut(CamelModel):
    id: UUID
    name: str
    logo: str
    domain: str
    ats: str
    hq: str
    flag: str
    conf: int
    open: int
    comp: str
    tracking: bool
    added: str

    @classmethod
    def from_model(cls, company: Company, open_roles: int) -> "CompanyOut":
        return cls(
            id=company.id,
            name=company.name,
            logo=company.logo_url or "",
            domain=company.domain or "",
            ats=company.ats or "",
            hq=company.hq_country or "",
            flag=_flag(company.hq_country),
            conf=company.hq_confidence or 0,
            open=open_roles,
            comp=company.comp_estimate or "",
            tracking=company.tracking,
            added=company.added_at.strftime("%b %Y"),
        )


class CompanyPatch(CamelModel):
    name: str | None = None
    ats: str | None = None
    domain: str | None = None
    hq_country: str | None = None
    comp_estimate: str | None = None
    status: str | None = None
    tracking: bool | None = None
