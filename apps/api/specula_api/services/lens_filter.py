"""Translate a lens into SQL predicates over the posting pool.

The production analog of the prototype's `filterByLens` (design spec §4.3): a lens's
structured `scope` / `modes` / `origin_rule` become `WHERE` clauses over `postings`.
Shared with the jobs-state lane. Counts are DERIVED by applying these predicates per
request — they are never stored as columns.
"""

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement

from specula_api.db.models import Lens, Posting

# A posting is "new" if first seen within this window (the only recency signal on the
# posting itself; the prototype's authored `isNew` flag has no server-side column).
NEW_WINDOW = timedelta(days=7)

_COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")


def _scope_predicate(scope: str | None) -> ColumnElement[bool] | None:
    """A location filter from a lens scope, or None for region-level / any scopes.

    Handles the two concrete shapes the model carries: a bare country code ("ES")
    and a "City, CC" form ("Berlin, DE"). Anything else (e.g. "EU", "Any region")
    is a soft/region scope with no hard location filter.
    """
    if not scope:
        return None
    scope = scope.strip()
    if _COUNTRY_CODE.match(scope):
        return Posting.country == scope
    if "," in scope:
        city = scope.split(",", 1)[0].strip()
        if city:
            return Posting.city == city
    return None


def lens_where(lens: Lens) -> list[ColumnElement[bool]]:
    """Predicates for the postings a lens matches. Empty list = no filter (default)."""
    if lens.is_default:
        return []

    predicates: list[ColumnElement[bool]] = []
    if lens.modes:
        predicates.append(Posting.work_mode.in_(lens.modes))
    if lens.origin_rule == "foreign_hq":
        predicates.append(Posting.hq_country != Posting.country)
    scope_predicate = _scope_predicate(lens.scope)
    if scope_predicate is not None:
        predicates.append(scope_predicate)
    return predicates


def new_predicate() -> ColumnElement[bool]:
    """True for postings first seen inside the `NEW_WINDOW`."""
    return Posting.first_seen_at >= datetime.now(UTC) - NEW_WINDOW
