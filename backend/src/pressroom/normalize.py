"""Pure-function normaliser: FetchedEntry + Source → Article.

No I/O.  All side-effectful work (DB writes, HTTP calls) happens elsewhere.
"""

import hashlib
import re
from datetime import UTC, datetime

import nh3

from pressroom.models import Article, FetchedEntry, Source

# ---------------------------------------------------------------------------
# HTML sanitisation config
# ---------------------------------------------------------------------------

_ALLOWED_TAGS: set[str] = {
    "p", "br",
    "a",
    "ul", "ol", "li",
    "strong", "em", "b", "i",
    "blockquote",
    "h2", "h3", "h4",
    "pre", "code",
}

_ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "a": {"href", "title"},
}

_EMPTY_TAG_SET: set[str] = set()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sanitize_html(raw: str) -> str | None:
    """Sanitise *raw* to the allowed tag allowlist; return None if empty after cleaning."""
    cleaned = nh3.clean(raw, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRIBUTES)
    return cleaned.strip() or None


def _to_plain_text(html: str) -> str | None:
    """Strip all HTML tags from already-sanitised *html* and collapse whitespace."""
    no_tags = re.sub(r"<[^>]+>", " ", html)
    text = " ".join(no_tags.split())
    return text or None


def _content_hash(url: str, title: str) -> str:
    """SHA-256 of ``url + '\\n' + title`` — unique dedup key across sources."""
    return hashlib.sha256(f"{url}\n{title}".encode()).hexdigest()


def _derive_external_id(entry: FetchedEntry) -> str:
    """Return a stable id using the fallback chain:

    1. Feed ``<guid>`` / ``<id>`` (``entry.external_id``)
    2. Canonical URL (``entry.url``)
    3. SHA-256 of ``url + '\\n' + title``
    """
    if entry.external_id:
        return entry.external_id
    if entry.url:
        return entry.url
    return _content_hash(entry.url, entry.title)


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Return *dt* as a timezone-aware UTC datetime, or None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize(entry: FetchedEntry, source: Source) -> Article:
    """Convert *entry* + *source* into a storage-ready :class:`Article`.

    The source must already have a database ``id`` assigned.
    """
    assert source.id is not None, "Source must have a database id before normalization"

    external_id = _derive_external_id(entry)

    body_html: str | None = None
    body_text: str | None = None
    body_html_raw: str | None = None

    if entry.body_html:
        body_html_raw = entry.body_html
        body_html = _sanitize_html(entry.body_html)
        if body_html:
            body_text = _to_plain_text(body_html)

    summary = entry.summary or None
    if summary and body_text and summary.strip() == body_text.strip():
        summary = None

    return Article(
        source_id=source.id,
        external_id=external_id,
        url=entry.url,
        title=entry.title,
        summary=summary,
        body_html=body_html,
        body_text=body_text,
        body_html_raw=body_html_raw,
        author=entry.author,
        language=source.language,
        published_at=_ensure_utc(entry.published_at),
        content_hash=_content_hash(entry.url, entry.title),
    )
