from specula_api.db.models import LlmCost, Run


def test_llm_cost_table_and_columns() -> None:
    assert LlmCost.__tablename__ == "llm_costs"
    cols = set(LlmCost.__table__.columns.keys())
    assert {"prompt_tokens", "completion_tokens", "embed_tokens"} <= cols
    assert "cost_usd" not in cols, "cost is no longer tracked (2026-07-29)"
    # tenancy FK cascades with the owning user
    fk = next(iter(LlmCost.__table__.c.user_id.foreign_keys))
    assert fk.ondelete == "CASCADE"


def test_run_has_no_cost_rollup() -> None:
    assert "cost_usd" not in set(Run.__table__.columns.keys())


def test_company_optout_and_run_rollups_exist() -> None:
    from specula_api.db.models import Company

    assert "opt_out" in Company.__table__.columns
    assert Company.__table__.c.opt_out.nullable is False
    assert "duration_ms" in set(Run.__table__.columns.keys())
