"""End-to-end integration test for the fetch pipeline.

Uses httpx.MockTransport to serve a fixture RSS feed without real HTTP calls.
Verifies that running the orchestrator twice inserts articles once and
produces zero duplicates on the second run.
"""

import asyncio
from pathlib import Path

import httpx
import pytest

from pressroom.db.repository import Repository
from pressroom.fetchers.rss import RssFetcher
from pressroom.models import Source
from pressroom.orchestrator import FetchOrchestrator

FIXTURES = Path(__file__).parent / "fixtures"


def _make_transport(fixture: str) -> httpx.AsyncBaseTransport:
    """Return an async transport that serves *fixture* for every request."""
    content = (FIXTURES / fixture).read_bytes()

    class _Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=content,
                headers={"content-type": "application/rss+xml; charset=utf-8"},
            )

    return _Transport()


def _count_entries(fixture: str) -> int:
    """Count <item> elements in a fixture file."""
    return (FIXTURES / fixture).read_text(encoding="utf-8").count("<item>")


def _make_source(source_id: int, fixture: str) -> Source:
    return Source(
        id=source_id,
        name="Integration Test Feed",
        feed_url=f"https://example.com/{fixture}",
        language="en",
    )


# ---------------------------------------------------------------------------
# gamestar_sample.xml — full body + summary entries
# ---------------------------------------------------------------------------


def test_first_run_inserts_all_entries(repo: Repository) -> None:
    """After one run the article count must equal the fixture entry count."""
    fixture = "gamestar_sample.xml"
    sid = repo.upsert_source(
        Source(name="GameStar Test", feed_url=f"https://example.com/{fixture}", language="de")
    )
    source = repo.get_source_by_id(sid)
    assert source is not None

    fetcher = RssFetcher(transport=_make_transport(fixture))
    orchestrator = FetchOrchestrator(repo, fetcher=fetcher)

    run = asyncio.run(orchestrator.run_once(source, triggered_by="cli"))

    expected = _count_entries(fixture)
    assert run.status == "ok"
    assert run.articles_seen == expected
    assert run.articles_new == expected
    assert run.articles_duplicate == 0
    assert repo.count_articles() == expected


def test_second_run_produces_zero_new_articles(repo: Repository) -> None:
    """Running the same feed twice must yield zero new articles on the second pass."""
    fixture = "gamestar_sample.xml"
    sid = repo.upsert_source(
        Source(name="GameStar Test", feed_url=f"https://example.com/{fixture}", language="de")
    )
    source = repo.get_source_by_id(sid)
    assert source is not None

    fetcher = RssFetcher(transport=_make_transport(fixture))
    orchestrator = FetchOrchestrator(repo, fetcher=fetcher)

    asyncio.run(orchestrator.run_once(source, triggered_by="cli"))
    run2 = asyncio.run(orchestrator.run_once(source, triggered_by="cli"))

    assert run2.articles_new == 0
    assert run2.articles_duplicate == _count_entries(fixture)


# ---------------------------------------------------------------------------
# summary_only.xml — entries with no content:encoded
# ---------------------------------------------------------------------------


def test_summary_only_feed_body_fields_are_none(repo: Repository) -> None:
    """Entries without content:encoded must produce articles with null body fields."""
    fixture = "summary_only.xml"
    sid = repo.upsert_source(
        Source(name="Summary Only Test", feed_url=f"https://example.com/{fixture}", language="en")
    )
    source = repo.get_source_by_id(sid)
    assert source is not None

    fetcher = RssFetcher(transport=_make_transport(fixture))
    orchestrator = FetchOrchestrator(repo, fetcher=fetcher)

    run = asyncio.run(orchestrator.run_once(source, triggered_by="cli"))

    expected = _count_entries(fixture)
    assert run.articles_new == expected

    items, _ = repo.list_articles()
    for article in items:
        assert article.body_html is None, f"Expected no body_html for {article.title!r}"
        assert article.body_text is None
        assert article.summary is not None


# ---------------------------------------------------------------------------
# fetch_runs record kept even on error
# ---------------------------------------------------------------------------


def test_fetch_run_recorded_on_error(repo: Repository) -> None:
    """A fetch_runs row must be written even when the feed returns an HTTP error."""

    class _ErrorTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, content=b"Internal Server Error")

    sid = repo.upsert_source(
        Source(name="Error Feed", feed_url="https://example.com/error.rss", language="en")
    )
    source = repo.get_source_by_id(sid)
    assert source is not None

    fetcher = RssFetcher(transport=_ErrorTransport())
    orchestrator = FetchOrchestrator(repo, fetcher=fetcher)

    run = asyncio.run(orchestrator.run_once(source, triggered_by="cli"))

    assert run.status == "error"
    assert run.error_message is not None
    # The run row must have been persisted
    last = repo.get_last_run_for_source(sid)
    assert last is not None
    assert last.status == "error"


# ---------------------------------------------------------------------------
# FTS search after insert
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("query,expected_count", [
    ("vollständige", 2),   # prefix matches both "vollständige" and "vollständigen" in fixture
    ("Summary", 2),        # "Summary" in both summary_only titles
])
def test_fts_search_after_fetch(query: str, expected_count: int, repo: Repository) -> None:
    """Articles inserted via the orchestrator must be findable via FTS search."""
    fixture = "gamestar_sample.xml" if "vollständige" in query else "summary_only.xml"
    lang = "de" if fixture == "gamestar_sample.xml" else "en"
    sid = repo.upsert_source(
        Source(name=f"FTS Test {fixture}", feed_url=f"https://fts.example.com/{fixture}", language=lang)
    )
    source = repo.get_source_by_id(sid)
    assert source is not None

    fetcher = RssFetcher(transport=_make_transport(fixture))
    orchestrator = FetchOrchestrator(repo, fetcher=fetcher)
    asyncio.run(orchestrator.run_once(source, triggered_by="cli"))

    results = repo.search_articles(query)
    assert len(results) == expected_count
