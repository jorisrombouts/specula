from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class TargetingIn(CamelModel):
    role_titles: list[str] = []
    seniority: list[str] = []
    must_haves: list[str] = []
    avoid: list[str] = []
    preferences: str | None = None


class TargetingOut(TargetingIn):
    model_config = ConfigDict(from_attributes=True)

    updated_at: datetime
