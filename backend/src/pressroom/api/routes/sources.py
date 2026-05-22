"""Routes for /api/sources."""

import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from pressroom.api.deps import get_orchestrator, get_repo
from pressroom.db.repository import Repository
from pressroom.models import FetchRun, Source
from pressroom.orchestrator import FetchOrchestrator

router = APIRouter(tags=["sources"])


# ---------------------------------------------------------------------------
# Response / request schemas
# ---------------------------------------------------------------------------


class SourceResponse(Source):
    """Source with last-run metadata appended."""

    last_run_status: Literal["running", "ok", "error", "not_modified"] | None = None
    last_run_articles_new: int | None = None
    last_run_finished_at: object = None  # datetime | None, kept as object for JSON


class CreateSourceBody(BaseModel):
    name: str
    feed_url: str
    feed_type: Literal["rss", "atom", "scraped"] = "rss"
    homepage_url: str | None = None
    category: str | None = None
    language: str | None = None
    fetch_interval_minutes: int = Field(default=60, ge=5)


class PatchSourceBody(BaseModel):
    is_active: bool | None = None
    fetch_interval_minutes: Annotated[int | None, Field(ge=5)] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enrich(source: Source, repo: Repository) -> SourceResponse:
    last_run = repo.get_last_run_for_source(source.id)  # type: ignore[arg-type]
    data = source.model_dump()
    if last_run is not None:
        data["last_run_status"] = last_run.status
        data["last_run_articles_new"] = last_run.articles_new
        data["last_run_finished_at"] = last_run.finished_at
    return SourceResponse.model_validate(data)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/sources")
def list_sources(repo: Repository = Depends(get_repo)) -> list[SourceResponse]:
    """Return all sources enriched with their most recent fetch-run metadata."""
    return [_enrich(s, repo) for s in repo.list_all_sources()]


@router.post("/sources", status_code=201)
def create_source(
    body: CreateSourceBody,
    repo: Repository = Depends(get_repo),
) -> Source:
    """Add a new source; returns 409 if the feed URL already exists."""
    source = Source.model_validate(body.model_dump())
    try:
        source_id = repo.insert_source(source)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="A source with that feed_url already exists.") from None
    fetched = repo.get_source_by_id(source_id)
    if fetched is None:
        raise HTTPException(status_code=500, detail="Source was created but could not be retrieved.")
    return fetched


@router.patch("/sources/{source_id}")
def patch_source(
    source_id: int,
    body: PatchSourceBody,
    repo: Repository = Depends(get_repo),
) -> Source:
    """Toggle is_active or update fetch_interval_minutes."""
    updated = repo.update_source_fields(
        source_id,
        is_active=body.is_active,
        fetch_interval_minutes=body.fetch_interval_minutes,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Source not found.")
    source = repo.get_source_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    return source


@router.post("/sources/{source_id}/fetch")
async def trigger_fetch(
    source_id: int,
    repo: Repository = Depends(get_repo),
    orchestrator: FetchOrchestrator = Depends(get_orchestrator),
) -> FetchRun:
    """Trigger an immediate fetch for one source; returns the completed FetchRun."""
    source = repo.get_source_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    return await orchestrator.run_once(source, triggered_by="manual")
