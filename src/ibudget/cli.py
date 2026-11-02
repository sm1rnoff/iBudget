import typer

from ibudget import __version__

app = typer.Typer(help="iBudget: track personal expenses.", no_args_is_help=True)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"ibudget {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version."
    ),
) -> None:
    """iBudget: track personal expenses."""
