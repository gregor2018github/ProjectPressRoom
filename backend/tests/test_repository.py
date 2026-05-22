"""Unit tests for pressroom.db.repository."""

import hashlib

from pressroom.db.repository import Repository
from pressroom.models import Article, FetchRun, InsertResult, Source


def _source(**kwargs: object) -> Source:
    defaults: dict[str, object] = {
        "name": "Test Source",
        "feed_url": "https://example.com/feed.xml",
        "language": "en",
    }
    defaults.update(kwargs)
    return Source.model_validate(defaults)


def _article(source_id: int, *, external_id: str = "guid-1", url: str = "https://example.com/1", title: str = "Article One") -> Article:
    content_hash = hashlib.sha256(f"{url}\n{title}".encode()).hexdigest()
    return Article(
        source_id=source_id,
        external_id=external_id,
        url=url,
        title=title,
        content_hash=content_hash,
    )


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


def test_upsert_source_inserts_new(repo: Repository) -> None:
    source_id = repo.upsert_source(_source())
    assert isinstance(source_id, int)
    assert source_id > 0


def test_upsert_source_returns_same_id_on_conflict(repo: Repository) -> None:
    s = _source()
    id1 = repo.upsert_source(s)
    id2 = repo.upsert_source(s)
    assert id1 == id2


def test_upsert_source_updates_name_on_conflict(repo: Repository) -> None:
    s = _source(name="Old Name")
    source_id = repo.upsert_source(s)

    updated = _source(name="New Name")
    repo.upsert_source(updated)

    fetched = repo.get_source_by_id(source_id)
    assert fetched is not None
    assert fetched.name == "New Name"


def test_upsert_source_preserves_is_active_on_conflict(repo: Repository) -> None:
    source_id = repo.upsert_source(_source(is_active=True))

    repo._conn.execute("UPDATE sources SET is_active = 0 WHERE id = ?", (source_id,))
    repo._conn.commit()

    repo.upsert_source(_source(is_active=True))

    fetched = repo.get_source_by_id(source_id)
    assert fetched is not None
    assert fetched.is_active is False


def test_list_active_sources_excludes_inactive(repo: Repository) -> None:
    repo.upsert_source(_source(name="Active", feed_url="https://a.com/feed.xml", is_active=True))
    repo.upsert_source(_source(name="Inactive", feed_url="https://b.com/feed.xml", is_active=False))

    active = repo.list_active_sources()
    names = [s.name for s in active]
    assert "Active" in names
    assert "Inactive" not in names


def test_get_source_by_id_returns_none_for_missing(repo: Repository) -> None:
    assert repo.get_source_by_id(9999) is None


def test_update_source_fetch_meta_persists_values(repo: Repository) -> None:
    source_id = repo.upsert_source(_source())
    repo.update_source_fetch_meta(
        source_id,
        etag='"abc123"',
        last_modified="Thu, 01 Jan 2025 00:00:00 GMT",
        last_status="ok",
        last_error=None,
    )
    fetched = repo.get_source_by_id(source_id)
    assert fetched is not None
    assert fetched.last_etag == '"abc123"'
    assert fetched.last_status == "ok"
    assert fetched.last_fetched_at is not None


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------


def test_insert_article_returns_new(repo: Repository) -> None:
    source_id = repo.upsert_source(_source())
    article = _article(source_id)
    assert repo.insert_article(article) == InsertResult.NEW


def test_insert_article_duplicate_external_id_same_source(repo: Repository) -> None:
    source_id = repo.upsert_source(_source())
    article = _article(source_id, external_id="guid-dup", url="https://example.com/dup", title="Dup")
    assert repo.insert_article(article) == InsertResult.NEW
    assert repo.insert_article(article) == InsertResult.DUPLICATE


def test_insert_article_duplicate_content_hash_different_source(repo: Repository) -> None:
    id1 = repo.upsert_source(_source(name="S1", feed_url="https://s1.com/feed.xml"))
    id2 = repo.upsert_source(_source(name="S2", feed_url="https://s2.com/feed.xml"))

    url, title = "https://shared.com/article", "Syndicated Article"
    a1 = _article(id1, external_id="guid-s1", url=url, title=title)
    a2 = _article(id2, external_id="guid-s2", url=url, title=title)

    assert repo.insert_article(a1) == InsertResult.NEW
    assert repo.insert_article(a2) == InsertResult.DUPLICATE


def test_article_exists_true_after_insert(repo: Repository) -> None:
    source_id = repo.upsert_source(_source())
    article = _article(source_id, external_id="exists-guid")
    repo.insert_article(article)
    assert repo.article_exists(source_id, "exists-guid") is True


def test_article_exists_false_when_not_inserted(repo: Repository) -> None:
    source_id = repo.upsert_source(_source())
    assert repo.article_exists(source_id, "ghost-guid") is False


# ---------------------------------------------------------------------------
# Fetch runs
# ---------------------------------------------------------------------------


def test_log_and_update_fetch_run_round_trip(repo: Repository) -> None:
    source_id = repo.upsert_source(_source())
    run = FetchRun(source_id=source_id, triggered_by="cli")
    run_id = repo.log_fetch_run(run)
    assert run_id > 0

    run.id = run_id
    run.status = "ok"
    run.http_status = 200
    run.articles_seen = 5
    run.articles_new = 3
    run.articles_duplicate = 2
    repo.update_fetch_run(run)

    row = repo._conn.execute(
        "SELECT status, http_status, articles_seen, articles_new, articles_duplicate, finished_at FROM fetch_runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    assert row is not None
    assert row["status"] == "ok"
    assert row["http_status"] == 200
    assert row["articles_seen"] == 5
    assert row["articles_new"] == 3
    assert row["articles_duplicate"] == 2
    assert row["finished_at"] is not None


def test_log_fetch_run_initial_status_is_running(repo: Repository) -> None:
    source_id = repo.upsert_source(_source())
    run = FetchRun(source_id=source_id, triggered_by="scheduler")
    run_id = repo.log_fetch_run(run)

    row = repo._conn.execute(
        "SELECT status FROM fetch_runs WHERE id = ?", (run_id,)
    ).fetchone()
    assert row is not None
    assert row["status"] == "running"


# ---------------------------------------------------------------------------
# FTS search
# ---------------------------------------------------------------------------


def test_search_articles_finds_known_title(repo: Repository) -> None:
    source_id = repo.upsert_source(_source())
    a = Article(
        source_id=source_id,
        external_id="fts-guid-1",
        url="https://example.com/fts-article",
        title="Unique Searchable Headline",
        body_text="The quick brown fox jumps over the lazy dog.",
        content_hash=hashlib.sha256(b"https://example.com/fts-article\nUnique Searchable Headline").hexdigest(),
    )
    repo.insert_article(a)

    results = repo.search_articles("Searchable")
    assert len(results) == 1
    article, snippet = results[0]
    assert article.title == "Unique Searchable Headline"
    assert isinstance(snippet, str)


def test_search_articles_returns_empty_for_no_match(repo: Repository) -> None:
    source_id = repo.upsert_source(_source())
    a = _article(source_id, url="https://example.com/nosearch", title="Nothing here")
    repo.insert_article(a)

    results = repo.search_articles("xyzzy_nonexistent_term")
    assert results == []


def test_search_articles_invalid_fts_syntax_returns_empty(repo: Repository) -> None:
    results = repo.search_articles("AND")
    assert results == []
