"""FastAPI application factory."""

from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pressroom.api.deps import get_repo
from pressroom.api.routes import articles, runs, sources
from pressroom.config import settings
from pressroom.db.repository import Repository

# Resolve the frontend/dist directory relative to this file's location.
# Layout: backend/src/pressroom/api/app.py → ../../../../frontend/dist
_FRONTEND_DIST = Path(__file__).parent.parent.parent.parent.parent / "frontend" / "dist"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Pressroom API",
        version="0.1.0",
        docs_url="/docs" if settings.dev else None,
        redoc_url=None,
    )

    if settings.dev:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/api/health", tags=["meta"])
    def health(repo: Repository = Depends(get_repo)) -> dict[str, object]:
        return {"status": "ok", "articles": repo.count_articles()}

    app.include_router(sources.router, prefix="/api")
    app.include_router(articles.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")

    # Serve the built frontend when the dist directory exists.
    # Unknown routes fall back to index.html so the SPA router handles them.
    if _FRONTEND_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str) -> FileResponse:
            index = _FRONTEND_DIST / "index.html"
            return FileResponse(str(index))

    return app
