"""Routes for /api/articles."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from pressroom.api.deps import get_repo
from pressroom.db.repository import Repository
from pressroom.models import Article

router = APIRouter(tags=["articles"])


# ---------------------------------------------------------------------------
# Response / request schemas
# ---------------------------------------------------------------------------


class ArticlePage(BaseModel):
    items: list[Article]
    total: int
    page: int
    page_size: int


class ArticleSearchHit(Article):
    snippet: str = ""


class PatchArticleBody(BaseModel):
    is_read: bool | None = None
    is_starred: bool | None = None


# ---------------------------------------------------------------------------
# Routes — /articles/search MUST be declared before /articles/{article_id}
# so FastAPI does not try to coerce "search" to int first.
# ---------------------------------------------------------------------------


@router.get("/articles")
def list_articles(
    source_id: Annotated[int | None, Query()] = None,
    language: Annotated[str | None, Query()] = None,
    from_date: Annotated[datetime | None, Query()] = None,
    to_date: Annotated[datetime | None, Query()] = None,
    is_read: Annotated[bool | None, Query()] = None,
    is_starred: Annotated[bool | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    repo: Repository = Depends(get_repo),
) -> ArticlePage:
    """Return paginated articles with optional filters."""
    items, total = repo.list_articles(
        source_id=source_id,
        language=language,
        from_date=from_date,
        to_date=to_date,
        is_read=is_read,
        is_starred=is_starred,
        page=page,
        page_size=page_size,
    )
    return ArticlePage(items=items, total=total, page=page, page_size=page_size)


@router.get("/articles/search")
def search_articles(
    q: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    repo: Repository = Depends(get_repo),
) -> list[ArticleSearchHit]:
    """Full-text search; results include a ``snippet`` with highlighted matches."""
    hits = repo.search_articles(q, limit=limit)
    return [
        ArticleSearchHit.model_validate({**article.model_dump(), "snippet": snippet})
        for article, snippet in hits
    ]


@router.get("/articles/{article_id}")
def get_article(
    article_id: int,
    repo: Repository = Depends(get_repo),
) -> Article:
    """Return a single article by id."""
    article = repo.get_article_by_id(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found.")
    return article


@router.patch("/articles/{article_id}")
def patch_article(
    article_id: int,
    body: PatchArticleBody,
    repo: Repository = Depends(get_repo),
) -> Article:
    """Update ``is_read`` and/or ``is_starred`` on an article."""
    updated = repo.patch_article(
        article_id, is_read=body.is_read, is_starred=body.is_starred
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Article not found.")
    article = repo.get_article_by_id(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found.")
    return article
