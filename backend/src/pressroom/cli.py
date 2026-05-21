"""pressroom CLI — entry point for all subcommands."""

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


if __name__ == "__main__":
    app()
