"""pressroom CLI — entry point for all subcommands."""

import tomllib
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    name="pressroom",
    help="Personal news collector and curation tool.",
    no_args_is_help=True,
)

db_app = typer.Typer(help="Database management commands.", no_args_is_help=True)
app.add_typer(db_app, name="db")

sources_app = typer.Typer(help="Source management commands.", no_args_is_help=True)
app.add_typer(sources_app, name="sources")


@app.callback()
def _main() -> None:
    """Personal news collector and curation tool."""


# ---------------------------------------------------------------------------
# pressroom db …
# ---------------------------------------------------------------------------


@db_app.command("init")
def db_init(
    db_path: Annotated[
        Path | None,
        typer.Option(help="Override the database path (default: settings.db_path)."),
    ] = None,
) -> None:
    """Create the database schema and apply any pending migrations."""
    from pressroom.config import settings
    from pressroom.db.connection import run_migrations

    target = db_path if db_path is not None else settings.db_path
    applied = run_migrations(target)
    if applied:
        typer.echo(f"Initialised {target} ({applied} migration(s) applied).")
    else:
        typer.echo(f"{target} is already up-to-date.")


# ---------------------------------------------------------------------------
# pressroom sources …
# ---------------------------------------------------------------------------


@sources_app.command("sync")
def sources_sync(
    sources_file: Annotated[
        Path,
        typer.Option(help="Path to the sources TOML file."),
    ] = Path("config/sources.toml"),
) -> None:
    """Upsert all sources from the TOML file into the database."""
    from pressroom.config import settings
    from pressroom.db.connection import get_connection
    from pressroom.db.repository import Repository
    from pressroom.models import Source

    if not sources_file.exists():
        typer.echo(f"Sources file not found: {sources_file}", err=True)
        raise typer.Exit(1)

    with sources_file.open("rb") as fh:
        data = tomllib.load(fh)

    raw_sources: list[dict[str, object]] = data.get("source", [])
    if not raw_sources:
        typer.echo("No [[source]] entries found in the file.")
        return

    conn = get_connection(settings.db_path)
    try:
        repo = Repository(conn)
        count = 0
        for raw in raw_sources:
            source = Source.model_validate(raw)
            repo.upsert_source(source)
            typer.echo(f"  synced: {source.name}")
            count += 1
        typer.echo(f"Synced {count} source(s) to {settings.db_path}.")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# pressroom fetch
# ---------------------------------------------------------------------------


@app.command("fetch")
def fetch(
    source_name: Annotated[
        str | None,
        typer.Option("--source", help="Fetch a specific source by name."),
    ] = None,
    all_sources: Annotated[
        bool,
        typer.Option("--all", help="Fetch all active sources."),
    ] = False,
) -> None:
    """Fetch articles from one source or all active sources."""
    import logging

    from pressroom.config import settings
    from pressroom.db.connection import get_connection
    from pressroom.db.repository import Repository
    from pressroom.orchestrator import FetchOrchestrator

    if not source_name and not all_sources:
        typer.echo("Specify --source NAME or --all.", err=True)
        raise typer.Exit(1)
    if source_name and all_sources:
        typer.echo("Cannot use --source and --all together.", err=True)
        raise typer.Exit(1)

    logging.basicConfig(level=settings.log_level)

    conn = get_connection(settings.db_path)
    try:
        repo = Repository(conn)
        orchestrator = FetchOrchestrator(repo)
        sources = repo.list_active_sources()

        if source_name:
            sources = [s for s in sources if s.name == source_name]
            if not sources:
                typer.echo(f"No active source named {source_name!r}.", err=True)
                raise typer.Exit(1)

        for source in sources:
            run = orchestrator.run_once_sync(source, triggered_by="cli")
            typer.echo(
                f"{source.name}: {run.status}"
                f" (seen={run.articles_seen}"
                f" new={run.articles_new}"
                f" dup={run.articles_duplicate})"
            )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# pressroom daemon
# ---------------------------------------------------------------------------


@app.command("daemon")
def daemon() -> None:
    """Start the background fetch scheduler (blocks until Ctrl-C)."""
    import logging

    from pressroom.config import settings
    from pressroom.db.connection import get_connection
    from pressroom.db.repository import Repository
    from pressroom.orchestrator import FetchOrchestrator
    from pressroom.scheduler import build_scheduler

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    conn = get_connection(settings.db_path)
    try:
        repo = Repository(conn)
        orchestrator = FetchOrchestrator(repo)
        scheduler = build_scheduler(repo, orchestrator)

        job_count = len(scheduler.get_jobs())
        typer.echo(f"Scheduler started with {job_count} job(s). Press Ctrl-C to stop.")

        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            if scheduler.running:
                scheduler.shutdown(wait=True)
            typer.echo("Scheduler stopped.")
    finally:
        conn.close()


if __name__ == "__main__":
    app()
