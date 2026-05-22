"""The only module that reads from or writes to SQLite.

All SQL uses parameterised queries — no string formatting anywhere.
"""

import sqlite3
from typing import Literal

from pressroom.models import Article, FetchRun, InsertResult, Source


def _to_source(row: sqlite3.Row) -> Source:
    return Source.model_validate(dict(row))


def _to_article(row: sqlite3.Row) -> Article:
    return Article.model_validate(dict(row))


class Repository:
    """Thin data-access layer over the pressroom SQLite database."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def upsert_source(self, source: Source) -> int:
        """Insert or update *source* by ``feed_url``; return the row id.

        On conflict, updates editable metadata (name, category, language,
        feed_type, homepage_url) but preserves ``is_active`` and
        ``fetch_interval_minutes`` so user changes survive re-syncs.
        """
        cursor = self._conn.execute(
            """
            INSERT INTO sources (
                name, feed_url, feed_type, homepage_url,
                category, language, is_active, fetch_interval_minutes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(feed_url) DO UPDATE SET
                name           = excluded.name,
                feed_type      = excluded.feed_type,
                homepage_url   = excluded.homepage_url,
                category       = excluded.category,
                language       = excluded.language,
                updated_at     = datetime('now')
            RETURNING id
            """,
            (
                source.name,
                source.feed_url,
                source.feed_type,
                source.homepage_url,
                source.category,
                source.language,
                1 if source.is_active else 0,
                source.fetch_interval_minutes,
            ),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("upsert_source did not return a row id")
        self._conn.commit()
        return int(row[0])

    def list_active_sources(self) -> list[Source]:
        """Return all sources where ``is_active = 1``, ordered by name."""
        cursor = self._conn.execute(
            "SELECT * FROM sources WHERE is_active = 1 ORDER BY name"
        )
        return [_to_source(row) for row in cursor]

    def get_source_by_id(self, source_id: int) -> Source | None:
        """Return the source with *source_id*, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
        return _to_source(row) if row is not None else None

    def update_source_fetch_meta(
        self,
        source_id: int,
        *,
        etag: str | None,
        last_modified: str | None,
        last_status: Literal["ok", "error", "not_modified"],
        last_error: str | None = None,
    ) -> None:
        """Persist HTTP cache headers and last-run outcome onto the source row."""
        self._conn.execute(
            """
            UPDATE sources
            SET last_etag       = ?,
                last_modified   = ?,
                last_fetched_at = datetime('now'),
                last_status     = ?,
                last_error      = ?,
                updated_at      = datetime('now')
            WHERE id = ?
            """,
            (etag, last_modified, last_status, last_error, source_id),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Articles
    # ------------------------------------------------------------------

    def insert_article(self, article: Article) -> InsertResult:
        """Insert *article*; return NEW or DUPLICATE on constraint violation.

        Both ``UNIQUE (source_id, external_id)`` and
        ``UNIQUE (content_hash)`` are treated as duplicates.
        """
        try:
            self._conn.execute(
                """
                INSERT INTO articles (
                    source_id, external_id, url, title, summary,
                    body_html, body_text, body_html_raw,
                    author, language, published_at,
                    content_hash, is_read, is_starred
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article.source_id,
                    article.external_id,
                    article.url,
                    article.title,
                    article.summary,
                    article.body_html,
                    article.body_text,
                    article.body_html_raw,
                    article.author,
                    article.language,
                    article.published_at.isoformat() if article.published_at else None,
                    article.content_hash,
                    1 if article.is_read else 0,
                    1 if article.is_starred else 0,
                ),
            )
            self._conn.commit()
            return InsertResult.NEW
        except sqlite3.IntegrityError:
            return InsertResult.DUPLICATE

    def article_exists(self, source_id: int, external_id: str) -> bool:
        """Return True if an article with this ``(source_id, external_id)`` exists."""
        row = self._conn.execute(
            "SELECT 1 FROM articles WHERE source_id = ? AND external_id = ?",
            (source_id, external_id),
        ).fetchone()
        return row is not None

    # ------------------------------------------------------------------
    # Fetch runs
    # ------------------------------------------------------------------

    def log_fetch_run(self, run: FetchRun) -> int:
        """Open a ``status='running'`` row; return the new row id."""
        cursor = self._conn.execute(
            """
            INSERT INTO fetch_runs (source_id, triggered_by)
            VALUES (?, ?)
            """,
            (run.source_id, run.triggered_by),
        )
        self._conn.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("log_fetch_run did not return a row id")
        return cursor.lastrowid

    def update_fetch_run(self, run: FetchRun) -> None:
        """Close the fetch-run row with final status, counts, and error message."""
        self._conn.execute(
            """
            UPDATE fetch_runs
            SET finished_at       = datetime('now'),
                status            = ?,
                http_status       = ?,
                articles_seen     = ?,
                articles_new      = ?,
                articles_duplicate = ?,
                error_message     = ?
            WHERE id = ?
            """,
            (
                run.status,
                run.http_status,
                run.articles_seen,
                run.articles_new,
                run.articles_duplicate,
                run.error_message,
                run.id,
            ),
        )
        self._conn.commit()
