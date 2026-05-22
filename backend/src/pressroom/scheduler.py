"""APScheduler-based background fetch scheduler."""

import logging
from collections.abc import Callable

from apscheduler.schedulers.blocking import BlockingScheduler

from pressroom.db.repository import Repository
from pressroom.models import Source
from pressroom.orchestrator import FetchOrchestrator

_log = logging.getLogger(__name__)


def _make_job(orchestrator: FetchOrchestrator, source: Source) -> Callable[[], None]:
    """Return a no-arg callable that runs the orchestrator for *source*."""

    def _job() -> None:
        orchestrator.run_once_sync(source, triggered_by="scheduler")

    return _job


def build_scheduler(repo: Repository, orchestrator: FetchOrchestrator) -> BlockingScheduler:
    """Create a :class:`BlockingScheduler` with one interval job per active source.

    Each job is configured with ``coalesce=True``, ``max_instances=1``, and
    ``jitter=30`` seconds to spread load across the minute boundary.
    """
    scheduler: BlockingScheduler = BlockingScheduler()
    sources = repo.list_active_sources()

    for source in sources:
        scheduler.add_job(
            _make_job(orchestrator, source),
            trigger="interval",
            minutes=source.fetch_interval_minutes,
            id=f"source-{source.id}",
            coalesce=True,
            max_instances=1,
            jitter=30,
        )
        _log.info(
            "Registered job: source=%r interval=%d min",
            source.name, source.fetch_interval_minutes,
        )

    return scheduler
