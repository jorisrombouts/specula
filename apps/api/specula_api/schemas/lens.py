from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class LensCreate(CamelModel):
    name: str
    short: str = ""
    scope: str = ""
    modes: list[str] = []
    origin: str = ""  # maps to the model's `origin_rule`
    focus: str = ""
    seeds: list[str] = []
    active: bool = True


class LensUpdate(CamelModel):
    name: str | None = None
    short: str | None = None
    scope: str | None = None
    modes: list[str] | None = None
    origin: str | None = None
    focus: str | None = None
    seeds: list[str] | None = None
    active: bool | None = None


class LensSummaryOut(CamelModel):
    id: UUID
    name: str
    short: str
    active: bool
    scope: str
    modes: list[str]
    origin: str
    focus: str
    seeds: list[str]
    # DERIVED server-side per request — never stored as columns (§4.3).
    count: int
    is_new: int
