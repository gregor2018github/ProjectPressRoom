"""API tests for /api/health and /api/sources."""

import hashlib

from fastapi.testclient import TestClient

from pressroom.db.repository import Repository
from pressroom.models import Article, Source


def _source(**kwargs: object) -> Source:
    defaults: dict[str, object] = {
        "name": "Test Feed",
        "feed_url": "https://example.com/feed.xml",
        "language": "en",
    }
    defaults.update(kwargs)
    return Source.model_validate(defaults)


def _article(source_id: int) -> Article:
    url, title = "https://example.com/a1", "Article One"
    return Article(
        source_id=source_id,
        external_id="guid-1",
        url=url,
        title=title,
        content_hash=hashlib.sha256(f"{url}\n{title}".encode()).hexdigest(),
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health_returns_ok_with_zero_articles(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "articles": 0}


def test_health_counts_articles(client: TestClient, repo: Repository) -> None:
    sid = repo.upsert_source(_source())
    repo.insert_article(_article(sid))
    resp = client.get("/api/health")
    assert resp.json()["articles"] == 1


# ---------------------------------------------------------------------------
# GET /api/sources
# ---------------------------------------------------------------------------


def test_list_sources_empty(client: TestClient) -> None:
    resp = client.get("/api/sources")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_sources_returns_all(client: TestClient, repo: Repository) -> None:
    repo.upsert_source(_source(name="Alpha", feed_url="https://a.com/f.xml", is_active=True))
    repo.upsert_source(_source(name="Beta", feed_url="https://b.com/f.xml", is_active=False))
    resp = client.get("/api/sources")
    names = [s["name"] for s in resp.json()]
    assert "Alpha" in names
    assert "Beta" in names


def test_list_sources_includes_last_run_fields(client: TestClient, repo: Repository) -> None:
    sid = repo.upsert_source(_source())
    from pressroom.models import FetchRun
    run = FetchRun(source_id=sid, triggered_by="cli")
    run_id = repo.log_fetch_run(run)
    run.id = run_id
    run.status = "ok"
    run.articles_new = 3
    repo.update_fetch_run(run)

    resp = client.get("/api/sources")
    source_data = resp.json()[0]
    assert source_data["last_run_status"] == "ok"
    assert source_data["last_run_articles_new"] == 3


# ---------------------------------------------------------------------------
# POST /api/sources
# ---------------------------------------------------------------------------


def test_create_source_returns_201(client: TestClient) -> None:
    payload = {"name": "New Feed", "feed_url": "https://new.com/feed.xml"}
    resp = client.post("/api/sources", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "New Feed"
    assert data["id"] is not None


def test_create_source_duplicate_returns_409(client: TestClient) -> None:
    payload = {"name": "Dup Feed", "feed_url": "https://dup.com/feed.xml"}
    client.post("/api/sources", json=payload)
    resp = client.post("/api/sources", json=payload)
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# PATCH /api/sources/{id}
# ---------------------------------------------------------------------------


def test_patch_source_is_active(client: TestClient, repo: Repository) -> None:
    sid = repo.upsert_source(_source(is_active=True))
    resp = client.patch(f"/api/sources/{sid}", json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_patch_source_not_found(client: TestClient) -> None:
    resp = client.patch("/api/sources/9999", json={"is_active": False})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/sources/{id}/fetch
# ---------------------------------------------------------------------------


def test_trigger_fetch_returns_fetch_run(client: TestClient, repo: Repository) -> None:
    sid = repo.upsert_source(_source())
    resp = client.post(f"/api/sources/{sid}/fetch")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_id"] == sid
    assert data["triggered_by"] == "manual"
    assert data["status"] in ("ok", "error", "not_modified")


def test_trigger_fetch_not_found(client: TestClient) -> None:
    resp = client.post("/api/sources/9999/fetch")
    assert resp.status_code == 404
