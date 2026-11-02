# iBudget

A simple command-line tool for managing personal expenses, with a small read-only web dashboard.

Record what you spend, group it into categories, set monthly budgets, import bank statements as CSV, and see monthly reports in the terminal or in the browser. All data stays on your machine in one SQLite file.

- Requirements: [docs/requirements.md](docs/requirements.md)
- How AI was used to build it: [docs/ai-journal.md](docs/ai-journal.md)

## Setup

Requires Python 3.14.

```bash
python3.14 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/ibudget --help
```

Data is stored in your user data directory. Set `IBUDGET_DB=/path/to/file.db` or pass `--db PATH` to use another database.

## Commands

| Command | What it does |
|---|---|
| `ibudget add AMOUNT CATEGORY [NOTE] [--date YYYY-MM-DD]` | Add an expense (date defaults to today) |
| `ibudget list [--month YYYY-MM \| --all] [--category C] [--min N] [--max N] [--sort date\|amount] [--limit N]` | List expenses of this month (or the given one) with a total |
| `ibudget edit ID [--amount] [--category] [--date] [--note]` | Change an expense |
| `ibudget delete ID [--yes]` | Delete an expense |
| `ibudget category list` | Categories with their number of expenses and budget |
| `ibudget category add NAME` | Add a category |
| `ibudget category rename OLD NEW` | Rename a category; its expenses and budget follow |
| `ibudget category delete NAME [--reassign-to C] [--yes]` | Delete a category; one that has expenses needs `--reassign-to` |
| `ibudget budget set CATEGORY AMOUNT` | Set a monthly budget; `add` warns at 90% and when it is exceeded |
| `ibudget budget list [--month YYYY-MM]` | Budgets with spent, left and % used |
| `ibudget budget remove CATEGORY` | Remove a budget |
| `ibudget report [--month YYYY-MM]` | Spending per category: share, budget usage and change vs the previous month |
| `ibudget config get [KEY]` / `ibudget config set KEY VALUE` | Show or change settings (`currency`, default `EUR`) |

## Development

```bash
.venv/bin/pytest                  # tests
.venv/bin/ruff check .            # lint
```
