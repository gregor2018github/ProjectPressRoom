"""Shared pytest fixtures and helpers."""

from collections.abc import Callable, Generator
from pathlib import Path

import httpx
import pytest

from pressroom.db.connection import get_connection, run_migrations
from pressroom.db.repository import Repository


def make_async_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.AsyncBaseTransport:
    """Wrap a sync request handler into an ``AsyncBaseTransport`` for testing."""

    class _AsyncTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return handler(request)

    return _AsyncTransport()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Return a path to a freshly migrated temporary SQLite database."""
    p = tmp_path / "test.sqlite"
    run_migrations(p)
    return p


@pytest.fixture
def repo(db_path: Path) -> Generator[Repository, None, None]:
    """Yield a :class:`Repository` backed by a temporary in-memory database."""
    conn = get_connection(db_path)
    try:
        yield Repository(conn)
    finally:
        conn.close()
