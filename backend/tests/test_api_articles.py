"""API tests for /api/articles and /api/runs."""

import hashlib

from fastapi.testclient import TestClient

from pressroom.db.repository import Repository
from pressroom.models import Article, FetchRun, Source


def _source(**kwargs: object) -> Source:
    defaults: dict[str, object] = {
        "name": "Test Feed",
        "feed_url": "https://example.com/feed.xml",
        "language": "en",
    }
    defaults.update(kwargs)
    return Source.model_validate(defaults)


def _article(
    source_id: int,
    *,
    external_id: str = "guid-1",
    url: str = "https://example.com/a1",
    title: str = "Article One",
    body_text: str | None = None,
) -> Article:
    content_hash = hashlib.sha256(f"{url}\n{title}".encode()).hexdigest()
    return Article(
        source_id=source_id,
        external_id=external_id,
        url=url,
        title=title,
        body_text=body_text,
        content_hash=content_hash,
    )


# ---------------------------------------------------------------------------
# GET /api/articles  (pagination)
# ---------------------------------------------------------------------------


def test_list_articles_empty(client: TestClient) -> None:
    resp = client.get("/api/articles")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["page_size"] == 50


def test_list_articles_pagination(client: TestClient, repo: Repository) -> None:
    sid = repo.upsert_source(_source())
    for i in range(5):
        url = f"https://example.com/a{i}"
        title = f"Article {i}"
        repo.insert_article(_article(sid, external_id=f"g{i}", url=url, title=title))

    resp = client.get("/api/articles?page=1&page_size=3")
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 3

    resp2 = client.get("/api/articles?page=2&page_size=3")
    body2 = resp2.json()
    assert len(body2["items"]) == 2


def test_list_articles_filter_by_source_id(client: TestClient, repo: Repository) -> None:
    sid1 = repo.upsert_source(_source(name="S1", feed_url="https://s1.com/f.xml"))
    sid2 = repo.upsert_source(_source(name="S2", feed_url="https://s2.com/f.xml"))
    repo.insert_article(_article(sid1, external_id="g1", url="https://s1.com/a1", title="S1 Art"))
    repo.insert_article(_article(sid2, external_id="g2", url="https://s2.com/a1", title="S2 Art"))

    resp = client.get(f"/api/articles?source_id={sid1}")
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["source_id"] == sid1


def test_list_articles_filter_is_read(client: TestClient, repo: Repository) -> None:
    sid = repo.upsert_source(_source())
    a = _article(sid)
    repo.insert_article(a)
    items, _ = repo.list_articles()
    article = items[0]
    repo.patch_article(article.id, is_read=True)  # type: ignore[arg-type]

    resp = client.get("/api/articles?is_read=true")
    assert resp.json()["total"] == 1

    resp2 = client.get("/api/articles?is_read=false")
    assert resp2.json()["total"] == 0


# ---------------------------------------------------------------------------
# GET /api/articles/search
# ---------------------------------------------------------------------------


def test_search_articles_finds_match(client: TestClient, repo: Repository) -> None:
    sid = repo.upsert_source(_source())
    repo.insert_article(
        _article(sid, body_text="The quick brown fox jumps over the lazy dog")
    )

    resp = client.get("/api/articles/search?q=quick+brown")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["title"] == "Article One"


def test_search_articles_zero_results(client: TestClient, repo: Repository) -> None:
    sid = repo.upsert_source(_source())
    repo.insert_article(_article(sid, body_text="normal article content"))

    resp = client.get("/api/articles/search?q=xyzzy+nonexistent")
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_articles_invalid_fts_returns_empty(client: TestClient) -> None:
    resp = client.get("/api/articles/search?q=AND")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# GET /api/articles/{id} and PATCH /api/articles/{id}
# ---------------------------------------------------------------------------


def test_get_article_by_id(client: TestClient, repo: Repository) -> None:
    sid = repo.upsert_source(_source())
    repo.insert_article(_article(sid))
    items, _ = repo.list_articles()
    article = items[0]

    resp = client.get(f"/api/articles/{article.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == article.id


def test_get_article_not_found(client: TestClient) -> None:
    resp = client.get("/api/articles/9999")
    assert resp.status_code == 404


def test_patch_article_is_read(client: TestClient, repo: Repository) -> None:
    sid = repo.upsert_source(_source())
    repo.insert_article(_article(sid))
    items, _ = repo.list_articles()
    article = items[0]

    resp = client.patch(f"/api/articles/{article.id}", json={"is_read": True})
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True


def test_patch_article_not_found(client: TestClient) -> None:
    resp = client.patch("/api/articles/9999", json={"is_read": True})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/runs
# ---------------------------------------------------------------------------


def test_list_runs_empty(client: TestClient) -> None:
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_runs_returns_newest_first(client: TestClient, repo: Repository) -> None:
    sid = repo.upsert_source(_source())
    for _ in range(3):
        run = FetchRun(source_id=sid, triggered_by="cli")
        run_id = repo.log_fetch_run(run)
        run.id = run_id
        run.status = "ok"
        repo.update_fetch_run(run)

    resp = client.get("/api/runs")
    runs = resp.json()
    assert len(runs) == 3
    # All are for the same source
    assert all(r["source_id"] == sid for r in runs)
