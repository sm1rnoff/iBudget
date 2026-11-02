from typer.testing import CliRunner

from ibudget import __version__
from ibudget.cli import app


def test_version():
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output
