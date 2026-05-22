"""Unit tests for pressroom.normalize."""

import hashlib
from datetime import UTC, datetime

from pressroom.models import FetchedEntry, Source
from pressroom.normalize import normalize

_SOURCE = Source(
    id=1,
    name="Test Source",
    feed_url="https://example.com/feed",
    language="en",
)


def _entry(**kwargs: object) -> FetchedEntry:
    defaults: dict[str, object] = {
        "external_id": "guid-default",
        "url": "https://example.com/article",
        "title": "Default Title",
    }
    defaults.update(kwargs)
    return FetchedEntry.model_validate(defaults)


# ---------------------------------------------------------------------------
# Full-entry normalisation
# ---------------------------------------------------------------------------


def test_full_entry_all_fields_mapped() -> None:
    pub = datetime(2025, 1, 20, 9, 0, 0, tzinfo=UTC)
    entry = _entry(
        external_id="guid-123",
        url="https://example.com/full",
        title="Full Article",
        summary="Short summary",
        body_html="<p>Full <strong>body</strong> text.</p>",
        author="Max Mustermann",
        published_at=pub,
    )

    article = normalize(entry, _SOURCE)

    assert article.source_id == 1
    assert article.external_id == "guid-123"
    assert article.url == "https://example.com/full"
    assert article.title == "Full Article"
    assert article.summary == "Short summary"
    assert article.body_html is not None
    assert article.body_text == "Full body text."
    assert article.body_html_raw == "<p>Full <strong>body</strong> text.</p>"
    assert article.author == "Max Mustermann"
    assert article.language == "en"
    assert article.published_at == pub
    assert len(article.content_hash) == 64


# ---------------------------------------------------------------------------
# Summary-only entry (no body)
# ---------------------------------------------------------------------------


def test_summary_only_entry_body_fields_are_none() -> None:
    entry = _entry(summary="Just a summary", body_html=None)

    article = normalize(entry, _SOURCE)

    assert article.summary == "Just a summary"
    assert article.body_html is None
    assert article.body_text is None
    assert article.body_html_raw is None


# ---------------------------------------------------------------------------
# external_id fallback chain
# ---------------------------------------------------------------------------


def test_external_id_uses_guid_when_present() -> None:
    entry = _entry(external_id="explicit-guid", url="https://example.com/x")
    assert normalize(entry, _SOURCE).external_id == "explicit-guid"


def test_external_id_fallback_to_url() -> None:
    entry = _entry(external_id=None, url="https://example.com/no-guid")
    assert normalize(entry, _SOURCE).external_id == "https://example.com/no-guid"


# ---------------------------------------------------------------------------
# content_hash
# ---------------------------------------------------------------------------


def test_content_hash_is_sha256_of_url_and_title() -> None:
    entry = _entry(url="https://example.com/hash-test", title="Hash Me")
    expected = hashlib.sha256(b"https://example.com/hash-test\nHash Me").hexdigest()
    assert normalize(entry, _SOURCE).content_hash == expected


def test_content_hash_is_independent_of_body() -> None:
    e1 = _entry(url="https://example.com/a", title="Same", body_html="<p>v1</p>")
    e2 = _entry(url="https://example.com/a", title="Same", body_html="<p>v2</p>")
    assert normalize(e1, _SOURCE).content_hash == normalize(e2, _SOURCE).content_hash


# ---------------------------------------------------------------------------
# HTML sanitisation
# ---------------------------------------------------------------------------


def test_script_tags_stripped() -> None:
    entry = _entry(body_html='<p>Safe</p><script>alert("xss")</script>')
    article = normalize(entry, _SOURCE)
    assert article.body_html is not None
    assert "<script>" not in article.body_html
    assert "alert" not in article.body_html
    assert "Safe" in article.body_html


def test_event_handlers_stripped() -> None:
    entry = _entry(body_html='<p onclick="evil()">Text</p>')
    article = normalize(entry, _SOURCE)
    assert article.body_html is not None
    assert "onclick" not in article.body_html
    assert "Text" in article.body_html


def test_allowed_tags_preserved() -> None:
    html = "<p>Para</p><strong>Bold</strong><em>Italic</em><blockquote>Quote</blockquote>"
    entry = _entry(body_html=html)
    article = normalize(entry, _SOURCE)
    assert article.body_html is not None
    for tag in ("p", "strong", "em", "blockquote"):
        assert f"<{tag}>" in article.body_html


def test_raw_html_preserved_before_sanitisation() -> None:
    raw = '<p>Clean</p><script>bad()</script>'
    entry = _entry(body_html=raw)
    article = normalize(entry, _SOURCE)
    assert article.body_html_raw == raw


# ---------------------------------------------------------------------------
# Timezone handling
# ---------------------------------------------------------------------------


def test_naive_published_at_gets_utc() -> None:
    naive = datetime(2025, 1, 1, 12, 0, 0)  # no tzinfo
    entry = _entry(published_at=naive)
    article = normalize(entry, _SOURCE)
    assert article.published_at is not None
    assert article.published_at.tzinfo is not None


def test_none_published_at_stays_none() -> None:
    entry = _entry(published_at=None)
    assert normalize(entry, _SOURCE).published_at is None
