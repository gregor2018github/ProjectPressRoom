"""The only module that reads from or writes to SQLite.

All SQL uses parameterised queries — no string formatting anywhere.
"""

import sqlite3
from datetime import datetime
from typing import Literal

from pressroom.models import Article, FetchRun, InsertResult, Source


def _to_source(row: sqlite3.Row) -> Source:
    return Source.model_validate(dict(row))


def _to_article(row: sqlite3.Row) -> Article:
    return Article.model_validate(dict(row))


def _to_fetch_run(row: sqlite3.Row) -> FetchRun:
    return FetchRun.model_validate(dict(row))


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

    def insert_source(self, source: Source) -> int:
        """Insert a new source; raise :exc:`sqlite3.IntegrityError` on duplicate.

        Unlike :meth:`upsert_source` this never overwrites an existing row.
        """
        cursor = self._conn.execute(
            """
            INSERT INTO sources (
                name, feed_url, feed_type, homepage_url,
                category, language, is_active, fetch_interval_minutes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
            raise RuntimeError("insert_source did not return a row id")
        self._conn.commit()
        return int(row[0])

    def list_active_sources(self) -> list[Source]:
        """Return all sources where ``is_active = 1``, ordered by name."""
        cursor = self._conn.execute(
            "SELECT * FROM sources WHERE is_active = 1 ORDER BY name"
        )
        return [_to_source(row) for row in cursor]

    def list_all_sources(self) -> list[Source]:
        """Return all sources regardless of ``is_active``, ordered by name."""
        cursor = self._conn.execute("SELECT * FROM sources ORDER BY name")
        return [_to_source(row) for row in cursor]

    def get_source_by_id(self, source_id: int) -> Source | None:
        """Return the source with *source_id*, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
        return _to_source(row) if row is not None else None

    def update_source_fields(
        self,
        source_id: int,
        *,
        is_active: bool | None = None,
        fetch_interval_minutes: int | None = None,
    ) -> bool:
        """Update editable user fields; return False if the source does not exist.

        Passing ``None`` for a field leaves it unchanged (COALESCE logic).
        """
        cursor = self._conn.execute(
            """
            UPDATE sources
            SET is_active              = COALESCE(?, is_active),
                fetch_interval_minutes = COALESCE(?, fetch_interval_minutes),
                updated_at             = datetime('now')
            WHERE id = ?
            """,
            (
                (1 if is_active else 0) if is_active is not None else None,
                fetch_interval_minutes,
                source_id,
            ),
        )
        self._conn.commit()
        return cursor.rowcount > 0

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

    def count_articles(self) -> int:
        """Return the total number of articles stored."""
        row = self._conn.execute("SELECT COUNT(*) FROM articles").fetchone()
        return int(row[0])

    def get_stats(self) -> dict[str, object]:
        """Return aggregate database statistics."""
        row = self._conn.execute(
            """
            SELECT
                COUNT(*)                          AS articles_total,
                SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) AS articles_unread,
                SUM(CASE WHEN is_starred = 1 THEN 1 ELSE 0 END) AS articles_starred,
                MIN(fetched_at)                   AS oldest_fetched_at,
                MAX(fetched_at)                   AS newest_fetched_at
            FROM articles
            """
        ).fetchone()
        sources_row = self._conn.execute(
            "SELECT COUNT(*) AS total, SUM(is_active) AS active FROM sources"
        ).fetchone()
        runs_row = self._conn.execute(
            "SELECT COUNT(*) FROM fetch_runs"
        ).fetchone()
        return {
            "articles_total": int(row["articles_total"] or 0),
            "articles_unread": int(row["articles_unread"] or 0),
            "articles_starred": int(row["articles_starred"] or 0),
            "oldest_fetched_at": row["oldest_fetched_at"],
            "newest_fetched_at": row["newest_fetched_at"],
            "sources_total": int(sources_row["total"] or 0),
            "sources_active": int(sources_row["active"] or 0),
            "fetch_runs_total": int(runs_row[0] or 0),
        }

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

    def list_articles(
        self,
        *,
        source_id: int | None = None,
        language: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        is_read: bool | None = None,
        is_starred: bool | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Article], int]:
        """Return a paginated list of articles and the unfiltered total count.

        All filter params are optional; passing ``None`` skips that filter.
        Results are ordered newest-first by ``published_at``.
        """
        params: dict[str, object] = {
            "source_id": source_id,
            "language": language,
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "is_read": (1 if is_read else 0) if is_read is not None else None,
            "is_starred": (1 if is_starred else 0) if is_starred is not None else None,
        }

        where = """
            WHERE (:source_id   IS NULL OR source_id   = :source_id)
              AND (:language     IS NULL OR language    = :language)
              AND (:from_date    IS NULL OR published_at >= :from_date)
              AND (:to_date      IS NULL OR published_at <= :to_date)
              AND (:is_read      IS NULL OR is_read      = :is_read)
              AND (:is_starred   IS NULL OR is_starred   = :is_starred)
        """

        total_row = self._conn.execute(
            f"SELECT COUNT(*) FROM articles {where}", params
        ).fetchone()
        total = int(total_row[0])

        rows = self._conn.execute(
            f"SELECT * FROM articles {where} ORDER BY published_at DESC LIMIT :limit OFFSET :offset",
            {**params, "limit": page_size, "offset": (page - 1) * page_size},
        ).fetchall()

        return [_to_article(row) for row in rows], total

    def get_article_by_id(self, article_id: int) -> Article | None:
        """Return the article with *article_id*, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM articles WHERE id = ?", (article_id,)
        ).fetchone()
        return _to_article(row) if row is not None else None

    def search_articles(
        self,
        query: str,
        limit: int = 50,
        *,
        source_id: int | None = None,
        author: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[tuple[Article, str]]:
        """Full-text search using FTS5; returns ``(article, snippet)`` pairs.

        The snippet highlights matched terms with ``<mark>...</mark>``.
        Optional filters narrow results after FTS ranking.
        Returns an empty list when *query* is invalid FTS5 syntax.
        """
        try:
            rows = self._conn.execute(
                """
                SELECT a.*,
                       snippet(articles_fts, 2, '<mark>', '</mark>', '…', 20) AS fts_snippet
                FROM   articles_fts
                JOIN   articles a ON articles_fts.rowid = a.id
                WHERE  articles_fts MATCH :query
                  AND  (:source_id IS NULL OR a.source_id    = :source_id)
                  AND  (:author    IS NULL OR a.author       = :author)
                  AND  (:from_date IS NULL OR a.published_at >= :from_date)
                  AND  (:to_date   IS NULL OR a.published_at <= :to_date)
                ORDER  BY rank
                LIMIT  :limit
                """,
                {
                    "query": query,
                    "source_id": source_id,
                    "author": author,
                    "from_date": from_date.isoformat() if from_date else None,
                    "to_date": to_date.isoformat() if to_date else None,
                    "limit": limit,
                },
            ).fetchall()
        except sqlite3.OperationalError:
            return []

        result: list[tuple[Article, str]] = []
        for row in rows:
            d = dict(row)
            snippet = str(d.pop("fts_snippet") or "")
            result.append((Article.model_validate(d), snippet))
        return result

    def patch_article(
        self,
        article_id: int,
        *,
        is_read: bool | None = None,
        is_starred: bool | None = None,
    ) -> bool:
        """Update read/starred state; return False if the article does not exist."""
        cursor = self._conn.execute(
            """
            UPDATE articles
            SET is_read    = COALESCE(?, is_read),
                is_starred = COALESCE(?, is_starred)
            WHERE id = ?
            """,
            (
                (1 if is_read else 0) if is_read is not None else None,
                (1 if is_starred else 0) if is_starred is not None else None,
                article_id,
            ),
        )
        self._conn.commit()
        return cursor.rowcount > 0

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

    def get_last_run_for_source(self, source_id: int) -> FetchRun | None:
        """Return the most recent fetch run for *source_id*, or None."""
        row = self._conn.execute(
            "SELECT * FROM fetch_runs WHERE source_id = ? ORDER BY started_at DESC LIMIT 1",
            (source_id,),
        ).fetchone()
        return _to_fetch_run(row) if row is not None else None

    def list_recent_runs(self, limit: int = 50) -> list[FetchRun]:
        """Return the *limit* most recent fetch runs across all sources, newest first."""
        rows = self._conn.execute(
            "SELECT * FROM fetch_runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_to_fetch_run(row) for row in rows]
