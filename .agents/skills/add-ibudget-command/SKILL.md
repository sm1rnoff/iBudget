---
name: add-ibudget-command
description: Adds or changes an `ibudget` CLI command the iBudget way — logic in a service, a thin Typer wrapper in cli.py, service and CliRunner tests, README command table and AI journal updated. Use whenever the user asks for a new ibudget command, subcommand or option, or to change what an existing command does or prints.
---

# Adding or changing an `ibudget` command

iBudget keeps the CLI and the web dashboard as thin layers over shared services (see `CLAUDE.md`). Follow these steps in order; do not skip the tests or the docs.

## 1. Decide where the logic goes

| Need | Put it in |
|---|---|
| New SQL query | a method on `Repository` in `src/ibudget/repository.py` (the only place with SQL) |
| Validation, calculations, rules | a function in `src/ibudget/services/<area>.py` (`expenses`, `categories`, `budgets`, `reports`, `csv_io`) or `config.py` |
| Parsing user text | reuse `money.parse_amount` / `parse_positive_amount`, `period.Month.parse`, `period.parse_date`, `categories.require` |
| Output formatting | `cli.py` only (Rich tables, `format_amount`) |

Rules:
- Money is integer cents everywhere; convert only with the `money` helpers.
- User mistakes raise `IBudgetError` with a message that says how to fix it (e.g. list the valid choices).
- If the dashboard should show the same data, the web route calls the same service function.

## 2. Write the service function first

```python
# src/ibudget/services/<area>.py
def do_thing(repo: Repository, category: str, amount: str) -> Result:
    found = categories.require(repo, category)  # raises IBudgetError with known names
    cents = parse_positive_amount(amount)
    ...
```

## 3. Add a thin Typer command

```python
@app.command()  # or @category_app / @budget_app / @config_app .command("name")
def thing(
    ctx: typer.Context,
    category: str = typer.Argument(..., help="Category name."),
    month: str | None = typer.Option(None, "--month", "-m", help="YYYY-MM (default: this month)."),
) -> None:
    """One-line help shown in `ibudget --help`."""
    with _session(ctx) as repo:  # opens the DB; IBudgetError -> red message, exit 1
        result = area.do_thing(repo, category, ...)
        console.print(f"[green]✔ ...[/green] {format_amount(result.cents, config.currency(repo))}")
```

- Always work inside `with _session(ctx) as repo:` so errors are clean and the DB is closed.
- Use `_month_option(month)` for `--month` options that default to the current month.
- Destructive commands ask `typer.confirm(...)` and offer `--yes`; validate *before* asking.
- A new command group: create `typer.Typer(help=..., no_args_is_help=True)` and `app.add_typer(...)`.

## 4. Test both layers

- Service test in `tests/test_<area>.py` using the `repo` and `add` fixtures from `tests/conftest.py`.
- CLI test in `tests/test_cli.py` with the `run(...)` fixture: the happy path, and at least one user error that must exit with code 1 and no `Traceback` (add it to `test_user_errors_exit_1_without_traceback` when it fits).
- Tests use a temporary database automatically (`IBUDGET_DB` is set by an autouse fixture). Never point a test at a real database.

## 5. Update docs

- Add or change the row in the **Commands** table in `README.md`.
- If it is a new requirement, add it to `docs/requirements.md` (functional requirements table and command overview).
- Add an entry to `docs/ai-journal.md` using the template at its top.

## 6. Verify before saying it is done

```bash
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
IBUDGET_DB=/tmp/ibudget-try.db .venv/bin/ibudget <command> --help
```

Run the new command once against a throwaway database and look at the output. Then commit with a message that says what the command does.
