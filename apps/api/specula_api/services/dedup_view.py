"""Read-side dedup: collapse a `dedup_group` to a single representative posting.

The pipeline's dedup stage clusters postings that are the same role reaching us from several
sources; this is the half that makes that visible. Spec §5: "Assign a shared `dedup_group`;
the pool is deduped on read." Applied to the jobs pool AND to every derived count, so a role
that happens to be listed twice cannot inflate a lens badge or skill demand.
"""

from collections.abc import Callable, Sequence

from specula_api.db.models import Posting


def _identity(item: Posting) -> Posting:
    return item


def _rank(posting: Posting) -> tuple[int, float]:
    """Best representative first: richest extraction, then most recently seen.

    A missing `extraction_confidence` sorts below a real 0 — an unextracted shell should never
    represent a group over a posting we actually read.
    """
    confidence = posting.extraction_confidence
    last_seen = posting.last_seen_at
    return (
        -1 if confidence is None else confidence,
        last_seen.timestamp() if last_seen is not None else float("-inf"),
    )


def collapse_duplicates[T](
    items: Sequence[T], posting_of: Callable[[T], Posting] | None = None
) -> list[T]:
    """One item per `dedup_group`, keeping the best-ranked member; ungrouped items all pass.

    Input order is preserved (each surviving group sits where its FIRST member appeared), so
    callers that sort afterwards are unaffected.
    """
    accessor: Callable[[T], Posting] = posting_of or _identity  # type: ignore[assignment]

    best_by_group: dict[object, T] = {}
    for item in items:
        group = accessor(item).dedup_group
        if group is None:
            continue
        incumbent = best_by_group.get(group)
        if incumbent is None or _rank(accessor(item)) > _rank(accessor(incumbent)):
            best_by_group[group] = item

    kept: list[T] = []
    emitted: set[object] = set()
    for item in items:
        group = accessor(item).dedup_group
        if group is None:
            kept.append(item)
            continue
        if group in emitted:
            continue
        emitted.add(group)
        kept.append(best_by_group[group])
    return kept
