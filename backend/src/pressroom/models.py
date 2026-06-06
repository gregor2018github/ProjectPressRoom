"""Pydantic models that are the shared type language across all pressroom modules.

Column names match the SQLite schema in ``db/schema.sql`` exactly so that
repository code can map rows to models without renaming fields.
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class InsertResult(Enum):
    """Return value of ``Repository.insert_article``."""

    NEW = "new"
    DUPLICATE = "duplicate"


# ---------------------------------------------------------------------------
# Core domain models
# ---------------------------------------------------------------------------


class Source(BaseModel):
    """A news source (RSS/Atom feed) tracked in the ``sources`` table."""

    id: int | None = Field(default=None, description="Auto-assigned primary key.")
    name: str = Field(description="Human-readable display name; unique across sources.")
    feed_url: str = Field(description="URL of the RSS or Atom feed; unique across sources.")
    feed_type: Literal["rss", "atom", "scraped"] = Field(
        default="rss",
        description="Feed format. Determines which fetcher adapter is used.",
    )
    homepage_url: str | None = Field(
        default=None,
        description="Optional URL of the source's main website.",
    )
    category: str | None = Field(
        default=None,
        description="Free-form label, e.g. 'tech', 'gaming', 'general'.",
    )
    language: str | None = Field(
        default=None,
        description="BCP-47 language code, e.g. 'en', 'de', 'nl'.",
    )
    is_active: bool = Field(
        default=True,
        description="Inactive sources are skipped by the scheduler and fetch commands.",
    )
    fetch_interval_minutes: int = Field(
        default=60,
        ge=5,
        description="Minimum minutes between fetches for this source.",
    )
    last_etag: str | None = Field(
        default=None,
        description="ETag from the most recent successful HTTP response; used for conditional GET.",
    )
    last_modified: str | None = Field(
        default=None,
        description="Last-Modified header from the most recent successful response.",
    )
    last_fetched_at: datetime | None = Field(
        default=None,
        description="Timestamp of the most recent completed fetch attempt (UTC ISO 8601).",
    )
    last_status: Literal["ok", "error", "not_modified"] | None = Field(
        default=None,
        description="Outcome of the most recent fetch run.",
    )
    last_error: str | None = Field(
        default=None,
        description="Error message from the most recent failed fetch, if any.",
    )
    created_at: datetime | None = Field(
        default=None,
        description="Row creation timestamp (set by the database).",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Row last-modified timestamp (set by the database).",
    )


class Article(BaseModel):
    """A single article stored in the ``articles`` table.

    The header / summary / body split is intentional:
    - ``title`` — the headline only.
    - ``summary`` — the feed-provided short description, if any.
    - ``body_html`` / ``body_text`` — the full article body, sanitised.
    - ``body_html_raw`` — the original unsanitised HTML, kept for debugging.
    """

    id: int | None = Field(default=None, description="Auto-assigned primary key.")
    source_id: int = Field(description="Foreign key to the source that provided this article.")
    external_id: str = Field(
        description="Stable identifier: feed guid/id, canonical URL, or a SHA-256 fallback.",
    )
    url: str = Field(description="Canonical link to the article.")
    title: str = Field(description="Article headline (the feed's <title>).")
    summary: str | None = Field(
        default=None,
        description="Short description from the feed (<description> or <summary>). May be None.",
    )
    body_html: str | None = Field(
        default=None,
        description="Sanitised HTML body. None when the feed only provides a summary.",
    )
    body_text: str | None = Field(
        default=None,
        description="Plain-text body derived from body_html by stripping tags.",
    )
    body_html_raw: str | None = Field(
        default=None,
        description="Original unsanitised HTML body, retained for debugging the cleaning pipeline.",
    )
    author: str | None = Field(default=None, description="Byline from the feed, if present.")
    language: str | None = Field(
        default=None,
        description="BCP-47 language code. Populated from the source until phase-2 auto-detection.",
    )
    published_at: datetime | None = Field(
        default=None,
        description="Publication timestamp from the feed (UTC). None if unparseable.",
    )
    fetched_at: datetime | None = Field(
        default=None,
        description="Timestamp when this article was stored. Defaults to database NOW() if None.",
    )
    content_hash: str = Field(
        description="SHA-256 of (url + '\\n' + title). Unique across sources to catch syndicates.",
    )
    is_read: bool = Field(default=False, description="True once the user has opened the article.")
    is_starred: bool = Field(default=False, description="User-set bookmark flag.")
    scraped_body_html: str | None = Field(
        default=None,
        description="Sanitised HTML extracted by the full-article scraper. None until scraped.",
    )
    scraped_body_text: str | None = Field(
        default=None,
        description="Plain-text version of scraped_body_html.",
    )
    scraped_at: datetime | None = Field(
        default=None,
        description="Timestamp of the most recent successful scrape (UTC).",
    )
    source_name: str | None = Field(default=None, description="Denormalised source name, populated by API read queries.")


class FetchedEntry(BaseModel):
    """Raw data for one feed entry as returned by a fetcher adapter.

    This is the *unnormalised* representation — it uses the feed's own field
    names and types. ``normalize.normalize()`` converts it into an ``Article``.
    """

    external_id: str | None = Field(
        default=None,
        description="Raw guid/id/url from the feed entry. None if the feed omits it.",
    )
    url: str = Field(description="Canonical link for this entry.")
    title: str = Field(description="Entry headline as supplied by the feed.")
    summary: str | None = Field(
        default=None,
        description="Short description from the feed, if present.",
    )
    body_html: str | None = Field(
        default=None,
        description="Full HTML body from the feed, if present (unsanitised at this stage).",
    )
    author: str | None = Field(default=None, description="Author name from the feed, if present.")
    published_at: datetime | None = Field(
        default=None,
        description="Publication date parsed from the feed entry. May be None.",
    )
    etag: str | None = Field(
        default=None,
        description="ETag response header from the HTTP fetch that produced this entry.",
    )
    last_modified: str | None = Field(
        default=None,
        description="Last-Modified response header from the HTTP fetch that produced this entry.",
    )


class FetchRun(BaseModel):
    """A record of one fetch attempt, stored in the ``fetch_runs`` table.

    A row is opened with ``status='running'`` at the start and closed with
    ``update_fetch_run`` regardless of success or failure.
    """

    id: int | None = Field(default=None, description="Auto-assigned primary key.")
    source_id: int = Field(description="The source this run was triggered for.")
    triggered_by: Literal["scheduler", "manual", "cli"] = Field(
        description="What initiated this fetch.",
    )
    started_at: datetime | None = Field(
        default=None,
        description="Run start timestamp (set by the database if None).",
    )
    finished_at: datetime | None = Field(
        default=None,
        description="Run completion timestamp. None while still running.",
    )
    status: Literal["running", "ok", "error", "not_modified"] = Field(
        default="running",
        description="Current state of this run.",
    )
    http_status: int | None = Field(
        default=None,
        description="HTTP status code returned by the feed server.",
    )
    articles_seen: int = Field(
        default=0,
        description="Total number of entries returned by the feed.",
    )
    articles_new: int = Field(
        default=0,
        description="Entries that were inserted as new articles.",
    )
    articles_duplicate: int = Field(
        default=0,
        description="Entries skipped because they already existed in the database.",
    )
    error_message: str | None = Field(
        default=None,
        description="Error detail when status is 'error'.",
    )
