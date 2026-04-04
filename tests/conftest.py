"""
Shared fixtures for the test suite.

Strategy: swap PostgreSQL for a temp-file SQLite database so tests run
without any external service. A named file (not :memory:) is required
because Flask closes the DB connection after every request via
teardown_appcontext. With :memory:, each reconnect creates a fresh
empty database — data would vanish between requests in the same test.
A temp file persists across open/close cycles.
"""
import os
import tempfile
from unittest.mock import patch

import pytest
from peewee import SqliteDatabase

from app.database import db


@pytest.fixture
def app():
    # Create a unique temp file for this test's SQLite database
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    tmp_path = tmp.name

    # Patch PostgresqlDatabase so init_db() initialises the proxy with
    # our SQLite instance instead of trying to reach a real Postgres server.
    with patch("app.database.PostgresqlDatabase") as MockPG:
        MockPG.return_value = SqliteDatabase(tmp_path)
        from app import create_app

        application = create_app()

    application.config["TESTING"] = True

    # Create tables outside any request context — Peewee handles its own
    # connection lifecycle for DDL operations.
    from app.models.event import Event
    from app.models.link import Link
    from app.models.user import User

    db.connect(reuse_if_open=True)
    db.create_tables([User, Link, Event])
    db.close()

    yield application

    # Teardown: drop tables and delete the temp file
    db.connect(reuse_if_open=True)
    db.drop_tables([User, Link, Event])
    db.close()
    os.unlink(tmp_path)


@pytest.fixture
def client(app):
    """Flask test client — use for HTTP-level integration tests."""
    return app.test_client()
