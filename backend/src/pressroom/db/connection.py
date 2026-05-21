"""SQLite connection factory and migration runner."""

import sqlite3
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"

_CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT NOT NULL PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Return a configured ``sqlite3.Connection`` for *db_path*.

    Enables WAL journal mode (better concurrent read performance) and
    foreign-key enforcement on every connection. The caller is responsible
    for closing the connection.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def run_migrations(db_path: Path) -> int:
    """Apply any pending migrations to *db_path* and return the count applied.

    Migration files are read from the ``migrations/`` directory next to this
    module, sorted alphabetically (``0001_…``, ``0002_…``, …).  Each applied
    version is recorded in ``schema_migrations`` so re-running is a no-op.
    """
    conn = get_connection(db_path)
    try:
        conn.execute(_CREATE_MIGRATIONS_TABLE)
        conn.commit()

        applied: set[str] = set()
        for row in conn.execute("SELECT version FROM schema_migrations"):
            applied.add(str(row[0]))

        count = 0
        for path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
            version = path.stem  # e.g. "0001_initial"
            if version in applied:
                continue
            conn.executescript(path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)", (version,)
            )
            conn.commit()
            count += 1

        return count
    finally:
        conn.close()
