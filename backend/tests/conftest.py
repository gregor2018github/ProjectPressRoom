"""Shared pytest fixtures and helpers."""

from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

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


@pytest.fixture
def client(db_path: Path) -> TestClient:
    """Return a :class:`TestClient` wired to a temporary test database.

    The ``get_db`` dependency is overridden so all requests use *db_path*.
    The ``get_orchestrator`` dependency is overridden with a mock fetcher
    that immediately returns an error to avoid real HTTP calls in tests.
    """
    from pressroom.api.app import create_app
    from pressroom.api.deps import get_db, get_orchestrator, get_repo
    from pressroom.fetchers.base import FetchResult
    from pressroom.orchestrator import FetchOrchestrator

    class _MockFetcher:
        async def fetch(self, source: Any) -> FetchResult:
            return FetchResult(error="mock: no network in tests")

    app = create_app()

    def _override_get_db() -> Generator[Any, None, None]:
        conn = get_connection(db_path)
        try:
            yield conn
        finally:
            conn.close()

    def _override_get_orchestrator(
        repo: Repository = Depends(get_repo),
    ) -> FetchOrchestrator:
        return FetchOrchestrator(repo, fetcher=_MockFetcher())

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_orchestrator] = _override_get_orchestrator
    return TestClient(app)
