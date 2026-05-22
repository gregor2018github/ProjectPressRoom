"""FastAPI application factory."""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pressroom.api.deps import get_repo
from pressroom.api.routes import articles, runs, sources
from pressroom.config import settings
from pressroom.db.repository import Repository


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

    return app
