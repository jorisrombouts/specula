from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class DiscoverySettingsIn(CamelModel):
    max_searches: int = Field(ge=1, le=20)


class DiscoverySettingsOut(CamelModel):
    max_searches: int
