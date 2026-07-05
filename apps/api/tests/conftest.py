import pytest
from alembic.config import Config

from alembic import command
from specula_api.db import models  # noqa: F401  (register models on Base.metadata)


@pytest.fixture(scope="session")
def migrated_db() -> None:
    command.upgrade(Config("alembic.ini"), "head")
