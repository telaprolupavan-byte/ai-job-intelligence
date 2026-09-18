import sys
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.api.database import engine
from apps.api.rate_limit import reset_rate_limits


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture
def db():
    """
    Yield a session bound to a SAVEPOINT nested inside an outer transaction.

    The outer transaction is always rolled back on teardown, so any data
    created by a test (even if the test code calls db.commit()) never
    persists to the real database.
    """
    connection = engine.connect()
    outer_transaction = connection.begin()

    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    session.begin_nested()

    def restart_savepoint(session_, transaction):
        if transaction.nested and not transaction._parent.nested:
            session_.begin_nested()

    event.listen(session, "after_transaction_end", restart_savepoint)

    try:
        yield session
    finally:
        event.remove(session, "after_transaction_end", restart_savepoint)
        session.close()
        outer_transaction.rollback()
        connection.close()