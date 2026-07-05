from sqlalchemy import DateTime

from specula_api.db.base import Base

PER_USER = {
    "candidate_profiles",
    "targeting",
    "user_settings",
    "lenses",
    "companies",
    "postings",
    "scores",
    "posting_state",
    "approvals",
    "runs",
}


def test_all_tables_registered() -> None:
    names = set(Base.metadata.tables)
    assert PER_USER | {"users", "skills_taxonomy"} <= names


def test_per_user_tables_have_user_id() -> None:
    for t in PER_USER:
        assert "user_id" in Base.metadata.tables[t].columns


def test_global_table_has_no_user_id() -> None:
    assert "user_id" not in Base.metadata.tables["skills_taxonomy"].columns


def test_invariants_no_forbidden_columns() -> None:
    assert "raw_snapshot_key" not in Base.metadata.tables["postings"].columns
    score_cols = set(Base.metadata.tables["scores"].columns.keys())
    assert {"factor_loc", "match", "overall"}.isdisjoint(score_cols)
    assert not any(c for c in Base.metadata.tables["targeting"].columns if "salary" in c.name)
    for t in ("lenses", "companies"):
        assert "count" not in Base.metadata.tables[t].columns


def test_all_datetime_columns_are_timezone_aware() -> None:
    # §4.1 uses `timestamptz` throughout; a naive `DateTime` would silently drift.
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, DateTime):
                assert col.type.timezone is True, f"{table.name}.{col.name} must be timestamptz"
