from specula_api.db.models import User


def test_user_table_name() -> None:
    assert User.__tablename__ == "users"


def test_user_has_exactly_the_expected_columns() -> None:
    cols = {c.name for c in User.__table__.columns}
    assert cols == {"id", "email", "name", "google_sub", "created_at"}


def test_user_email_and_google_sub_are_unique() -> None:
    assert User.__table__.c.email.unique is True
    assert User.__table__.c.google_sub.unique is True


def test_user_has_no_billing_columns() -> None:
    cols = {c.name for c in User.__table__.columns}
    assert "plan" not in cols
    assert "stripe_customer_id" not in cols
