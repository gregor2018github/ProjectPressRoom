"""pressroom CLI — entry point for all subcommands."""

import typer

app = typer.Typer(
    name="pressroom",
    help="Personal news collector and curation tool.",
    no_args_is_help=True,
)


@app.callback()
def _main() -> None:
    """Personal news collector and curation tool."""


if __name__ == "__main__":
    app()
