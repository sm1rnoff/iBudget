import datetime as dt

import pytest
from typer.testing import CliRunner

from ibudget.cli import app
from ibudget.period import Month


@pytest.fixture
def run():
    runner = CliRunner()

    def _run(*args: str, input: str | None = None):
        return runner.invoke(app, list(args), input=input)

    return _run


def test_add_and_list(run):
    result = run("add", "12,50", "Food", "Lunch with team", "--date", "2026-11-02")
    assert result.exit_code == 0, result.output
    assert "Added #1  12.50 EUR  food  2026-11-02" in result.output

    run("add", "45", "transport", "--date", "2026-11-01")
    run("add", "9.99", "food", "--date", "2026-10-15")

    result = run("list", "--month", "2026-11")
    assert result.exit_code == 0
    assert "November 2026" in result.output
    assert "Lunch with team" in result.output
    assert "57.50" in result.output  # total
    assert "9.99" not in result.output

    result = run("list", "--all", "--sort", "amount", "--category", "food")
    assert result.output.index("12.50") < result.output.index("9.99")
    assert "45.00" not in result.output


def test_add_defaults_to_today(run):
    run("add", "3", "food")
    result = run("list")
    assert dt.date.today().isoformat() in result.output
    assert Month.current().label in result.output


def test_list_empty_month(run):
    result = run("list", "--month", "2020-01")
    assert result.exit_code == 0
    assert "No expenses for January 2020." in result.output


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("add", "abc", "food"), "not a valid amount"),
        (("add", "0", "food"), "greater than zero"),
        (("add", "5", "pets"), "Unknown category 'pets'"),
        (("add", "5", "food", "--date", "2026-02-30"), "not a valid date"),
        (("list", "--month", "11-2026"), "YYYY-MM"),
        (("list", "--month", "2026-11", "--all"), "either --month or --all"),
        (("edit", "99", "--amount", "5"), "There is no expense #99"),
        (("delete", "99", "--yes"), "There is no expense #99"),
    ],
)
def test_user_errors_exit_1_without_traceback(run, args, message):
    result = run(*args)
    assert result.exit_code == 1
    assert message in result.output
    assert "Traceback" not in result.output


def test_edit(run):
    run("add", "12.50", "food", "Lunch", "--date", "2026-11-02")
    result = run("edit", "1", "--amount", "14", "--category", "other", "--note", "Dinner")
    assert result.exit_code == 0
    assert 'Updated #1  14.00 EUR  other  2026-11-02  "Dinner"' in result.output

    result = run("edit", "1")
    assert result.exit_code == 1
    assert "Nothing to change" in result.output


def test_delete_asks_for_confirmation(run):
    run("add", "12.50", "food")
    result = run("delete", "1", input="n\n")
    assert result.exit_code == 1  # aborted
    assert "12.50" in run("list").output

    result = run("delete", "1", input="y\n")
    assert result.exit_code == 0
    assert "Deleted #1" in result.output
    assert "No expenses" in run("list").output


def test_category_commands(run):
    assert run("category", "add", "Pets").exit_code == 0
    assert run("category", "rename", "pets", "pet care").exit_code == 0
    run("add", "20", "pet care", "--date", "2026-11-01")

    result = run("category", "list")
    assert "pet care" in result.output

    result = run("category", "delete", "pet care", "--yes")
    assert result.exit_code == 1
    assert "has 1 expense(s)" in result.output

    result = run("category", "delete", "pet care", "--reassign-to", "other", input="y\n")
    assert result.exit_code == 0
    assert "moving 1 expense(s) to other" in result.output
    assert "pet care" not in run("category", "list").output
    assert "other" in run("list", "--month", "2026-11").output


def test_config_commands(run):
    assert "currency = EUR" in run("config", "get").output
    assert run("config", "set", "currency", "bgn").exit_code == 0
    assert "currency = BGN" in run("config", "get", "currency").output
    assert "BGN" in run("add", "5", "food").output
    assert run("config", "set", "colour", "red").exit_code == 1


def test_db_option(run, tmp_path):
    other = tmp_path / "other.db"
    run("--db", str(other), "add", "5", "food")
    assert other.exists()
    assert "No expenses" in run("list").output  # the default (IBUDGET_DB) database is untouched
