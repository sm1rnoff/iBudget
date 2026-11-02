"""The `ibudget` command line. Parses input, calls services, prints results; no business logic."""

from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ibudget import __version__, config
from ibudget.errors import IBudgetError
from ibudget.models import Expense
from ibudget.money import format_amount
from ibudget.period import Month, parse_date
from ibudget.repository import Repository
from ibudget.services import categories, expenses

app = typer.Typer(help="iBudget: track personal expenses.", no_args_is_help=True)
category_app = typer.Typer(help="List, add, rename and delete categories.", no_args_is_help=True)
config_app = typer.Typer(help="Show or change settings.", no_args_is_help=True)
app.add_typer(category_app, name="category")
app.add_typer(config_app, name="config")

console = Console()
err_console = Console(stderr=True)


class SortBy(StrEnum):
    date = "date"
    amount = "amount"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"ibudget {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    db: Path | None = typer.Option(
        None, "--db", help="Database file (default: $IBUDGET_DB or the user data directory)."
    ),
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version."
    ),
) -> None:
    """iBudget: track personal expenses."""
    ctx.obj = {"db": db}


@contextmanager
def _session(ctx: typer.Context) -> Iterator[Repository]:
    """Open the database for one command and turn user errors into a clean message + exit 1."""
    repo = None
    try:
        repo = Repository.open(ctx.obj["db"])
        yield repo
    except IBudgetError as error:
        err_console.print(f"[red]Error:[/red] {error}")
        raise typer.Exit(1) from None
    finally:
        if repo is not None:
            repo.close()


def _describe(expense: Expense, currency: str) -> str:
    note = f'  "{expense.note}"' if expense.note else ""
    amount = format_amount(expense.amount_cents, currency)
    return f"#{expense.id}  {amount}  {expense.category}  {expense.date.isoformat()}{note}"


# --- expenses -------------------------------------------------------------


@app.command()
def add(
    ctx: typer.Context,
    amount: str = typer.Argument(..., help="Amount, e.g. 12.50 or 12,50."),
    category: str = typer.Argument(..., help="Category name."),
    note: str = typer.Argument("", help="Optional note."),
    date: str | None = typer.Option(None, "--date", "-d", help="YYYY-MM-DD (default: today)."),
) -> None:
    """Add an expense."""
    with _session(ctx) as repo:
        expense = expenses.add(repo, amount, category, note, parse_date(date) if date else None)
        console.print(f"[green]✔ Added[/green] {_describe(expense, config.currency(repo))}")


@app.command("list")
def list_(
    ctx: typer.Context,
    month: str | None = typer.Option(None, "--month", "-m", help="YYYY-MM (default: this month)."),
    all_months: bool = typer.Option(False, "--all", "-a", help="All months."),
    category: str | None = typer.Option(None, "--category", "-c", help="Only this category."),
    min_amount: str | None = typer.Option(None, "--min", help="Minimum amount."),
    max_amount: str | None = typer.Option(None, "--max", help="Maximum amount."),
    sort: SortBy = typer.Option(SortBy.date, "--sort", "-s", help="Sort newest or largest first."),
    limit: int | None = typer.Option(None, "--limit", "-n", min=1, help="Show at most N rows."),
) -> None:
    """List expenses."""
    with _session(ctx) as repo:
        if all_months and month:
            raise IBudgetError("Use either --month or --all, not both.")
        period = None if all_months else (Month.parse(month) if month else Month.current())
        found = expenses.find(
            repo,
            month=period,
            category=category,
            min_amount=min_amount,
            max_amount=max_amount,
            sort=sort.value,
            limit=limit,
        )
        title = period.label if period else "All expenses"
        if not found:
            console.print(f"No expenses for {title}.")
            return
        currency = config.currency(repo)
        table = Table(title=title, show_footer=True)
        table.add_column("ID", justify="right")
        table.add_column("Date")
        table.add_column("Category", footer="Total")
        total = sum(e.amount_cents for e in found)
        table.add_column(f"Amount ({currency})", justify="right", footer=format_amount(total))
        table.add_column("Note")
        for e in found:
            table.add_row(
                str(e.id), e.date.isoformat(), e.category, format_amount(e.amount_cents), e.note
            )
        console.print(table)


@app.command()
def edit(
    ctx: typer.Context,
    expense_id: int = typer.Argument(..., metavar="ID", help="Expense ID (see `ibudget list`)."),
    amount: str | None = typer.Option(None, "--amount", help="New amount."),
    category: str | None = typer.Option(None, "--category", "-c", help="New category."),
    date: str | None = typer.Option(None, "--date", "-d", help="New date, YYYY-MM-DD."),
    note: str | None = typer.Option(None, "--note", help='New note (use "" to clear).'),
) -> None:
    """Change an expense."""
    with _session(ctx) as repo:
        expense = expenses.edit(
            repo,
            expense_id,
            amount=amount,
            category=category,
            date=parse_date(date) if date else None,
            note=note,
        )
        console.print(f"[green]✔ Updated[/green] {_describe(expense, config.currency(repo))}")


@app.command()
def delete(
    ctx: typer.Context,
    expense_id: int = typer.Argument(..., metavar="ID", help="Expense ID (see `ibudget list`)."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Do not ask for confirmation."),
) -> None:
    """Delete an expense."""
    with _session(ctx) as repo:
        description = _describe(expenses.get(repo, expense_id), config.currency(repo))
        if not yes and not typer.confirm(f"Delete {description}?"):
            raise typer.Abort()
        expenses.delete(repo, expense_id)
        console.print(f"[green]✔ Deleted[/green] {description}")


# --- categories -----------------------------------------------------------


@category_app.command("list")
def category_list(ctx: typer.Context) -> None:
    """List categories with their number of expenses and monthly budget."""
    with _session(ctx) as repo:
        currency = config.currency(repo)
        table = Table()
        table.add_column("Category")
        table.add_column("Expenses", justify="right")
        table.add_column(f"Budget ({currency})", justify="right")
        for row in categories.overview(repo):
            budget = format_amount(row.budget_cents) if row.budget_cents else "—"
            table.add_row(row.name, str(row.expense_count), budget)
        console.print(table)


@category_app.command("add")
def category_add(ctx: typer.Context, name: str = typer.Argument(..., help="New category.")) -> None:
    """Add a category."""
    with _session(ctx) as repo:
        category = categories.add(repo, name)
        console.print(f"[green]✔ Added category[/green] {category.name}")


@category_app.command("rename")
def category_rename(
    ctx: typer.Context,
    old: str = typer.Argument(..., help="Current name."),
    new: str = typer.Argument(..., help="New name."),
) -> None:
    """Rename a category. Its expenses and budget keep belonging to it."""
    with _session(ctx) as repo:
        category = categories.rename(repo, old, new)
        console.print(f"[green]✔ Renamed[/green] {old} → {category.name}")


@category_app.command("delete")
def category_delete(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Category to delete."),
    reassign_to: str | None = typer.Option(
        None, "--reassign-to", "-r", help="Move this category's expenses here first."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Do not ask for confirmation."),
) -> None:
    """Delete a category (and its budget)."""
    with _session(ctx) as repo:
        plan = categories.check_delete(repo, name, reassign_to)
        moving = ""
        if plan.expense_count and plan.reassign_to:
            moving = f" (moving {plan.expense_count} expense(s) to {plan.reassign_to.name})"
        if not yes and not typer.confirm(f"Delete category '{plan.category.name}'{moving}?"):
            raise typer.Abort()
        categories.delete(repo, name, reassign_to)
        console.print(f"[green]✔ Deleted category[/green] {plan.category.name}{moving}")


# --- config ---------------------------------------------------------------


@config_app.command("get")
def config_get(
    ctx: typer.Context, key: str | None = typer.Argument(None, help="Setting name.")
) -> None:
    """Show one setting, or all of them."""
    with _session(ctx) as repo:
        values = {key: config.get(repo, key)} if key else config.all_settings(repo)
        for name, value in values.items():
            console.print(f"{name} = {value}")


@config_app.command("set")
def config_set(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Setting name, e.g. currency."),
    value: str = typer.Argument(..., help="New value."),
) -> None:
    """Change a setting."""
    with _session(ctx) as repo:
        console.print(f"[green]✔[/green] {key} = {config.set(repo, key, value)}")
