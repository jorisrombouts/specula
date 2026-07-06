from sqlalchemy import ColumnElement

from specula_api.db.models import Lens, Posting


def is_default_lens(lens: Lens | None) -> bool:
    """The default ('All') lens applies no filter: either flagged `is_default` or carrying
    neither a mode restriction nor an origin rule."""
    if lens is None:
        return True
    return bool(lens.is_default) or (not lens.modes and not lens.origin_rule)


def lens_where(lens: Lens | None) -> list[ColumnElement[bool]]:
    """SQL predicates that scope the shared pool to a lens (§5). Shared with the lenses
    lane. Currently understands two rules: a `modes` membership filter and the
    `foreign_hq` origin rule (posting HQ differs from its location)."""
    if is_default_lens(lens):
        return []
    assert lens is not None  # narrowed by is_default_lens
    conds: list[ColumnElement[bool]] = []
    if lens.modes:
        conds.append(Posting.work_mode.in_(lens.modes))
    if lens.origin_rule == "foreign_hq":
        conds.append(Posting.hq_country != Posting.country)
    return conds
