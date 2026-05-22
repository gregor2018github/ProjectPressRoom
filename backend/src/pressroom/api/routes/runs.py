"""Routes for /api/runs."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from pressroom.api.deps import get_repo
from pressroom.db.repository import Repository
from pressroom.models import FetchRun

router = APIRouter(tags=["runs"])


@router.get("/runs")
def list_runs(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    repo: Repository = Depends(get_repo),
) -> list[FetchRun]:
    """Return the most recent fetch runs across all sources, newest first."""
    return repo.list_recent_runs(limit=limit)
