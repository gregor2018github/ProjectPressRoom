"""Fetcher protocol and FetchResult returned by every fetcher adapter."""

from dataclasses import dataclass, field
from typing import Protocol

from pressroom.models import FetchedEntry, Source


@dataclass
class FetchResult:
    """Result of one feed fetch attempt.

    *entries* is empty when *not_modified* is True or when *error* is set.
    *etag* and *last_modified* carry the HTTP response headers so the
    orchestrator can persist them back onto the source for the next fetch.
    """

    entries: list[FetchedEntry] = field(default_factory=list)
    not_modified: bool = False
    etag: str | None = None
    last_modified: str | None = None
    error: str | None = None


class Fetcher(Protocol):
    """Minimal interface that every feed-fetcher adapter must implement."""

    async def fetch(self, source: Source) -> FetchResult:
        """Fetch *source* and return a :class:`FetchResult`."""
        ...
