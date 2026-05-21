"""Tests for pressroom.fetchers.rss."""

from pathlib import Path

import httpx
from tests.conftest import make_async_transport

from pressroom.fetchers.rss import RssFetcher
from pressroom.models import Source

_FIXTURE = Path(__file__).parent / "fixtures" / "gamestar_sample.xml"

_SOURCE = Source(
    id=1,
    name="GameStar (Gaming)",
    feed_url="https://www.gamestar.de/rss/gaming.rss",
    language="de",
)


async def test_parses_entries_from_fixture() -> None:
    xml_bytes = _FIXTURE.read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=xml_bytes,
            headers={"Content-Type": "application/rss+xml", "ETag": '"abc123"'},
        )

    result = await RssFetcher(transport=make_async_transport(handler)).fetch(_SOURCE)

    assert result.error is None
    assert result.not_modified is False
    assert result.etag == '"abc123"'
    assert len(result.entries) == 2

    first = result.entries[0]
    assert first.title == "Test-Spiel im Test: Großartig oder nicht?"
    assert first.external_id == "gamestar-article-1234567"
    assert first.body_html is not None
    assert "<p>" in first.body_html
    assert first.author is not None
    assert first.published_at is not None
    assert first.etag == '"abc123"'

    second = result.entries[1]
    assert second.title == "Nur-Summary Artikel ohne vollständigen Text"
    assert second.external_id is None  # no guid → falls back later in normalizer
    assert second.body_html is None
    assert second.author is None


async def test_sends_conditional_get_headers() -> None:
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(304)

    source = Source(
        id=1,
        name="GameStar (Gaming)",
        feed_url="https://www.gamestar.de/rss/gaming.rss",
        last_etag='"stale-etag"',
        last_modified="Mon, 01 Jan 2024 00:00:00 GMT",
    )

    result = await RssFetcher(transport=make_async_transport(handler)).fetch(source)

    assert result.not_modified is True
    assert result.entries == []
    assert captured_headers.get("if-none-match") == '"stale-etag"'
    assert captured_headers.get("if-modified-since") == "Mon, 01 Jan 2024 00:00:00 GMT"


async def test_not_modified_with_no_prior_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(304)

    result = await RssFetcher(transport=make_async_transport(handler)).fetch(_SOURCE)

    assert result.not_modified is True
    assert result.entries == []


async def test_http_error_returned_as_error_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not Found")

    result = await RssFetcher(transport=make_async_transport(handler)).fetch(_SOURCE)

    assert result.error is not None
    assert result.entries == []
