"""Fetch orchestrator: the only place where fetcher + normaliser + repository meet."""

import asyncio
import logging
from typing import Literal

from pressroom.db.repository import Repository
from pressroom.fetchers.base import Fetcher
from pressroom.fetchers.rss import RssFetcher
from pressroom.models import FetchRun, InsertResult, Source
from pressroom.normalize import normalize

_log = logging.getLogger(__name__)


class FetchOrchestrator:
    """Coordinates one full fetch cycle for a single source.

    Instantiate with a :class:`Repository` and an optional custom fetcher
    (defaults to :class:`RssFetcher`).  Inject a mock fetcher in tests.
    """

    def __init__(self, repo: Repository, fetcher: Fetcher | None = None) -> None:
        self._repo = repo
        self._fetcher: Fetcher = fetcher if fetcher is not None else RssFetcher()

    async def run_once(
        self,
        source: Source,
        triggered_by: Literal["scheduler", "manual", "cli"] = "scheduler",
    ) -> FetchRun:
        """Fetch *source*, normalise entries, persist to DB, return the completed run.

        A ``fetch_runs`` row is written regardless of success or failure.
        """
        assert source.id is not None, "Source must have a DB id before orchestration"

        run = FetchRun(source_id=source.id, triggered_by=triggered_by)
        run.id = self._repo.log_fetch_run(run)

        articles_seen = 0
        articles_new = 0
        articles_duplicate = 0
        status: Literal["ok", "error", "not_modified"] = "ok"
        error_message: str | None = None
        http_status: int | None = None
        etag: str | None = None
        last_modified: str | None = None

        try:
            result = await self._fetcher.fetch(source)
            etag = result.etag
            last_modified = result.last_modified

            if result.error:
                status = "error"
                error_message = result.error
            elif result.not_modified:
                status = "not_modified"
                http_status = 304
            else:
                http_status = 200
                articles_seen = len(result.entries)
                for entry in result.entries:
                    try:
                        article = normalize(entry, source)
                        insert_result = self._repo.insert_article(article)
                        if insert_result == InsertResult.NEW:
                            articles_new += 1
                        else:
                            articles_duplicate += 1
                    except Exception as exc:
                        _log.warning("Skipping entry from %s: %s", source.name, exc)

        except Exception as exc:
            status = "error"
            error_message = str(exc)
            _log.error("Fetch failed for source %s: %s", source.name, exc)

        # Preserve existing cache headers on error or not_modified — only update
        # them when we got a fresh 200 response with potentially new values.
        if status == "ok":
            self._repo.update_source_fetch_meta(
                source.id,
                etag=etag,
                last_modified=last_modified,
                last_status=status,
                last_error=None,
            )
        else:
            self._repo.update_source_fetch_meta(
                source.id,
                etag=source.last_etag,
                last_modified=source.last_modified,
                last_status=status,
                last_error=error_message,
            )

        run.status = status
        run.http_status = http_status
        run.articles_seen = articles_seen
        run.articles_new = articles_new
        run.articles_duplicate = articles_duplicate
        run.error_message = error_message
        self._repo.update_fetch_run(run)

        _log.info(
            "source=%s status=%s seen=%d new=%d dup=%d",
            source.name, status, articles_seen, articles_new, articles_duplicate,
        )
        return run

    def run_once_sync(
        self,
        source: Source,
        triggered_by: Literal["scheduler", "manual", "cli"] = "scheduler",
    ) -> FetchRun:
        """Synchronous wrapper around :meth:`run_once` for use by APScheduler jobs."""
        return asyncio.run(self.run_once(source, triggered_by=triggered_by))
