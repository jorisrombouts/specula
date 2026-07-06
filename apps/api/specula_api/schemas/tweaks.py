from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

# Enums mirror the unions in apps/web/src/lib/tweaks-init.ts. A PUT outside these
# values is rejected (422) so a bad client can't poison the JSONB store.
Mstyle = Literal["bars", "figure", "ring"]
Layout = Literal["rows", "cards"]
Density = Literal["comfortable", "compact"]
Accent = Literal["#2E7D4F", "#2D5BBF", "#9A7A18", "#7A4FB0"]
Font = Literal["Spectral", "Newsreader", "Source Serif 4"]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class TweaksIn(CamelModel):
    mstyle: Mstyle = "bars"
    layout: Layout = "rows"
    density: Density = "comfortable"
    accent: Accent = "#2E7D4F"
    font: Font = "Spectral"


class TweaksOut(TweaksIn):
    pass
