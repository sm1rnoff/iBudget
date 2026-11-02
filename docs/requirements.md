# iBudget — Requirements

## Idea

iBudget is a local, single-user command-line tool for personal expenses. You record what you spend, group it into categories, set a monthly budget per category, import bank statements, and see where your money goes — in the terminal or in a small read-only browser dashboard.

All data stays on your machine in one SQLite file. There is no account, no server and no cloud sync.

## Users and main scenarios

- **Daily logging:** `ibudget add 12.50 food "Lunch"` right after paying, with a warning when the food budget is nearly used up.
- **Monthly review:** `ibudget report` at the end of the month, or `ibudget serve` to look at the same numbers as bars and tables in the browser.
- **Catching up:** import the month's bank statement CSV instead of typing every expense; re-importing the same file never creates duplicates.
- **Housekeeping:** adjust categories as habits change — add, rename or delete them, moving existing expenses elsewhere.

## Functional requirements

| ID | Requirement |
|---|---|
| FR1 | Add an expense: amount, category, optional note, optional date (default today). |
| FR2 | List expenses filtered by month, category and amount range; sort by date or amount; show the total. |
| FR3 | Edit any field of an expense by ID; delete an expense by ID (with confirmation, `--yes` to skip it). |
| FR4 | Categories: seeded defaults (food, transport, housing, utilities, health, entertainment, shopping, other). The user can add, rename and delete categories. Names are case-insensitive and unique. Deleting a category that still has expenses fails and reports how many, unless `--reassign-to C` moves them to another category; the deleted category's budget is removed. |
| FR5 | Budgets: set, list and remove a monthly limit per category. After `add`, warn when the category has used at least 90% of its budget or exceeded it. |
| FR6 | Monthly report: total per category, share of the month, budget and its usage, change vs the previous month, grand total. |
| FR7 | CSV import with column mapping, a date format option, a default category, duplicate detection, a `--dry-run` preview and a summary of imported and skipped rows. |
| FR8 | CSV export of all expenses or a single month, to stdout or a file. |
| FR9 | Config: the currency code shown in output (default `EUR`), changed with `ibudget config set currency BGN`. No conversion between currencies. |
| FR10 | `ibudget serve` starts a read-only HTMX dashboard on `127.0.0.1`: month switcher, summary cards, category breakdown, budget bars, 6-month trend and an expense table with a category filter and sorting, all updated in place without full page reloads. |

## Non-functional requirements

| ID | Requirement |
|---|---|
| NFR1 | Python 3.14; installable as a package with `pip install -e .`; the command is `ibudget`. |
| NFR2 | Money is stored as integer cents, never floats. Amounts are parsed with `Decimal` and accept both `12.5` and `12,50`. |
| NFR3 | The database lives in the platform data directory and can be overridden with the `IBUDGET_DB` environment variable or the `--db` option. Tests never touch real data. |
| NFR4 | Invalid input gives a clear message and a non-zero exit code, never a stack trace. |
| NFR5 | The CLI and the dashboard are thin layers over one shared core. Neither contains business logic or SQL. |
| NFR6 | The dashboard is read-only, binds to localhost only, and needs no JavaScript beyond HTMX. |
| NFR7 | Every module has automated tests; `ruff` reports no issues; core coverage is at least 85%. |

## Out of scope

Multiple users and authentication, currency conversion, editing data in the web UI, cloud sync, and a CI pipeline.

## Command overview

```
ibudget add AMOUNT CATEGORY [NOTE] [--date YYYY-MM-DD]
ibudget list [--month YYYY-MM] [--category C] [--min N] [--max N] [--sort date|amount] [--limit N]
ibudget edit ID [--amount] [--category] [--date] [--note]
ibudget delete ID [--yes]
ibudget category list | add NAME | rename OLD NEW | delete NAME [--reassign-to C] [--yes]
ibudget budget set CATEGORY AMOUNT | list | remove CATEGORY
ibudget report [--month YYYY-MM]
ibudget import FILE [--map date=Col,amount=Col,note=Col,category=Col] [--date-format FMT]
                    [--default-category C] [--dry-run]
ibudget export [--month YYYY-MM] [--output FILE]
ibudget config get|set KEY [VALUE]
ibudget serve [--host 127.0.0.1] [--port 8000]
ibudget --version              # global option: --db PATH
```

## Modules

| # | Module | Code |
|---|---|---|
| 1 | CLI layer | `src/ibudget/cli.py` |
| 2 | Data layer | `src/ibudget/db.py`, `models.py`, `repository.py` |
| 3 | Core logic | `src/ibudget/services/` (categories, budgets, reports), `money.py` |
| 4 | Import/export | `src/ibudget/services/csv_io.py` |
| 5 | Web dashboard (HTMX) | `src/ibudget/web/` |
| 6 | Testing | `tests/` |
