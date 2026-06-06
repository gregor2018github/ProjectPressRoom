"""RSS / Atom fetcher adapter built on feedparser + httpx."""

import re
from datetime import UTC, datetime
from typing import Any

import feedparser
import httpx

from pressroom.fetchers.base import FetchResult
from pressroom.http_client import get_client, retry_on_transient
from pressroom.models import FetchedEntry, Source


@retry_on_transient
async def _get_feed(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
) -> httpx.Response:
    """GET *url* and raise for 4xx/5xx; 304 is returned as-is."""
    response = await client.get(url, headers=headers)
    if response.status_code != 304:
        response.raise_for_status()
    return response


def _parse_entry(
    entry: Any,
    etag: str | None,
    last_modified: str | None,
) -> FetchedEntry | None:
    """Convert one feedparser entry dict into a :class:`FetchedEntry`.

    Returns *None* when the entry lacks a usable URL or title.
    """
    url: str = str(entry.get("link") or "").strip()
    if not url:
        return None

    title: str = str(entry.get("title") or "").strip()
    if not title:
        return None

    external_id: str | None = entry.get("id") or entry.get("guid") or None

    summary_raw: Any = entry.get("summary")
    # feedparser sets summary_detail.type='text/html' for all RSS 2.0 <description>
    # fields regardless of actual content, so the type field is not a reliable signal.
    # Checking for literal '<' tags is the only robust way to detect HTML summaries.
    summary_is_html: bool = bool(summary_raw and "<" in str(summary_raw))

    summary: str | None = None
    html_summary: str | None = None  # HTML from <description>; body_html fallback

    if summary_raw:
        s = str(summary_raw).strip()
        if summary_is_html:
            html_summary = s
            # Strip tags to produce a clean plain-text teaser for the summary field.
            summary = " ".join(re.sub(r"<[^>]+>", " ", s).split()) or None
        else:
            summary = s or None

    # Atom <content> / RSS <content:encoded> lives in entry.content[]
    body_html: str | None = None
    content_list: Any = entry.get("content")
    if content_list:
        first: Any = content_list[0] if content_list else None
        if first:
            value: Any = first.get("value")
            body_html = str(value) if value else None

    # Promote HTML summary to body when no richer content:encoded is available.
    if body_html is None:
        body_html = html_summary

    author_raw: Any = entry.get("author")
    author: str | None = str(author_raw).strip() if author_raw else None

    published_at: datetime | None = None
    parsed_time: Any = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed_time is not None:
        try:
            published_at = datetime(
                int(parsed_time[0]),
                int(parsed_time[1]),
                int(parsed_time[2]),
                int(parsed_time[3]),
                int(parsed_time[4]),
                int(parsed_time[5]),
                tzinfo=UTC,
            )
        except (TypeError, ValueError, IndexError):
            published_at = None

    return FetchedEntry(
        external_id=external_id,
        url=url,
        title=title,
        summary=summary,
        body_html=body_html,
        author=author,
        published_at=published_at,
        etag=etag,
        last_modified=last_modified,
    )


class RssFetcher:
    """Fetcher adapter for RSS 2.0 and Atom feeds via feedparser.

    Pass *transport* to inject a mock transport in tests.
    """

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def fetch(self, source: Source) -> FetchResult:
        """Fetch *source* and return a :class:`FetchResult`.

        Sends conditional GET headers (If-None-Match / If-Modified-Since) when
        the source has cached ETag / Last-Modified values.  On 304 the result
        has ``not_modified=True`` and an empty entry list.
        """
        headers: dict[str, str] = {}
        if source.last_etag:
            headers["If-None-Match"] = source.last_etag
        if source.last_modified:
            headers["If-Modified-Since"] = source.last_modified

        try:
            async with get_client(transport=self._transport) as client:
                response = await _get_feed(client, source.feed_url, headers)
        except Exception as exc:
            return FetchResult(error=str(exc))

        if response.status_code == 304:
            return FetchResult(not_modified=True)

        etag: str | None = response.headers.get("etag")
        last_modified: str | None = response.headers.get("last-modified")

        parsed: Any = feedparser.parse(response.text)

        entries: list[FetchedEntry] = []
        for raw_entry in parsed.entries:
            fetched = _parse_entry(raw_entry, etag, last_modified)
            if fetched is not None:
                entries.append(fetched)

        return FetchResult(entries=entries, etag=etag, last_modified=last_modified)
