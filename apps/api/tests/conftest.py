import pytest
from alembic.config import Config

from alembic import command


@pytest.fixture(scope="session")
def migrated_db() -> None:
    command.upgrade(Config("alembic.ini"), "head")
