"""Read-side dedup: a `dedup_group` collapses to ONE representative posting.

The pipeline assigns groups; nothing consumed them, so duplicates were still shown and still
counted. Spec §5: "Assign a shared `dedup_group`; the pool is deduped on read."
"""

import uuid
from datetime import UTC, datetime

from specula_api.db.models import Posting
from specula_api.services.dedup_view import collapse_duplicates


def _posting(*, conf: int | None, last_seen: int, group: uuid.UUID | None = None) -> Posting:
    return Posting(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        source="greenhouse",
        source_url=f"https://example.test/{last_seen}",
        content_hash=f"hash-{uuid.uuid4()}",
        extraction_confidence=conf,
        last_seen_at=datetime(2026, 7, last_seen, tzinfo=UTC),
        dedup_group=group,
    )


def test_ungrouped_postings_all_pass_through() -> None:
    postings = [_posting(conf=90, last_seen=1), _posting(conf=80, last_seen=2)]

    assert collapse_duplicates(postings) == postings


def test_group_collapses_to_the_highest_confidence_member() -> None:
    group = uuid.uuid4()
    best = _posting(conf=95, last_seen=1, group=group)
    worse = _posting(conf=40, last_seen=9, group=group)

    # Ordering must not matter — a later-seen but worse extraction must not win.
    assert collapse_duplicates([worse, best]) == [best]
    assert collapse_duplicates([best, worse]) == [best]


def test_confidence_ties_break_on_most_recently_seen() -> None:
    group = uuid.uuid4()
    older = _posting(conf=90, last_seen=1, group=group)
    newer = _posting(conf=90, last_seen=5, group=group)

    assert collapse_duplicates([older, newer]) == [newer]


def test_a_missing_confidence_never_beats_a_real_one() -> None:
    group = uuid.uuid4()
    unextracted = _posting(conf=None, last_seen=9, group=group)
    extracted = _posting(conf=10, last_seen=1, group=group)

    assert collapse_duplicates([unextracted, extracted]) == [extracted]


def test_distinct_groups_each_keep_a_representative() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    a1 = _posting(conf=90, last_seen=1, group=a)
    a2 = _posting(conf=50, last_seen=2, group=a)
    b1 = _posting(conf=70, last_seen=3, group=b)
    loose = _posting(conf=60, last_seen=4)

    kept = collapse_duplicates([a1, a2, b1, loose])

    assert set(kept) == {a1, b1, loose}


def test_relative_order_of_survivors_is_preserved() -> None:
    """jobs.py collapses BEFORE sorting; a stable pass-through keeps that sort meaningful."""
    group = uuid.uuid4()
    first = _posting(conf=60, last_seen=1)
    rep = _posting(conf=95, last_seen=2, group=group)
    dup = _posting(conf=10, last_seen=3, group=group)
    last = _posting(conf=70, last_seen=4)

    assert collapse_duplicates([first, rep, dup, last]) == [first, rep, last]


def test_accepts_rows_via_a_posting_accessor() -> None:
    """jobs.py carries (Posting, Company, Score, PostingState) tuples, not bare postings."""
    group = uuid.uuid4()
    best = _posting(conf=95, last_seen=1, group=group)
    worse = _posting(conf=40, last_seen=2, group=group)
    rows = [(worse, "co-b"), (best, "co-a")]

    assert collapse_duplicates(rows, posting_of=lambda row: row[0]) == [(best, "co-a")]
