from specula_api.db.models import LlmCost


def test_llm_cost_table_and_columns() -> None:
    assert LlmCost.__tablename__ == "llm_costs"
    cols = set(LlmCost.__table__.columns.keys())
    assert cols == {
        "id",
        "user_id",
        "run_id",
        "company_id",
        "stage",
        "model",
        "prompt_tokens",
        "completion_tokens",
        "embed_tokens",
        "cost_usd",
        "created_at",
    }
    # tenancy FK cascades with the owning user
    fk = next(iter(LlmCost.__table__.c.user_id.foreign_keys))
    assert fk.ondelete == "CASCADE"


def test_company_optout_and_run_rollups_exist() -> None:
    from specula_api.db.models import Company, Run

    assert "opt_out" in Company.__table__.columns
    assert Company.__table__.c.opt_out.nullable is False
    assert {"cost_usd", "duration_ms"} <= set(Run.__table__.columns.keys())
    assert Run.__table__.c.cost_usd.nullable is True
