"""FastAPI dependency functions — injected into route handlers."""

import sqlite3
from collections.abc import Generator

from fastapi import Depends

from pressroom.config import settings
from pressroom.db.connection import get_connection
from pressroom.db.repository import Repository
from pressroom.orchestrator import FetchOrchestrator


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Yield a SQLite connection; close it when the request is done."""
    conn = get_connection(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


def get_repo(conn: sqlite3.Connection = Depends(get_db)) -> Repository:
    """Return a :class:`Repository` bound to the request's connection."""
    return Repository(conn)


def get_orchestrator(repo: Repository = Depends(get_repo)) -> FetchOrchestrator:
    """Return a :class:`FetchOrchestrator` bound to the request's repository."""
    return FetchOrchestrator(repo)
