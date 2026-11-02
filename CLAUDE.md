# iBudget

Personal expense tracker: the `ibudget` CLI plus a read-only HTMX dashboard (`ibudget serve`). Requirements are in `docs/requirements.md`; read them before changing behaviour.

## Stack

- Python 3.14, package in `src/ibudget/`, installed editable into `.venv`.
- Typer + Rich for the CLI; FastAPI + Jinja2 + HTMX for the dashboard; SQLite through the standard `sqlite3` module.
- pytest (+ pytest-cov, httpx2 for FastAPI's TestClient) and ruff.

## Commands

```bash
python3.14 -m venv .venv && .venv/bin/pip install -e ".[dev]"   # first-time setup
.venv/bin/pytest                    # all tests
.venv/bin/pytest --cov=ibudget      # with coverage
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/ibudget --help
IBUDGET_DB=/tmp/demo.db .venv/bin/ibudget serve
```

Always use `.venv/bin/...` or `python3.14`. Plain `python3` on this machine is the system Python 3.9 and will not work.

## Architecture rules

- `cli.py` and `web/` are thin layers: parse input, call a service, render output. No SQL and no business logic there.
- All SQL lives in `repository.py`. Services in `services/` hold the logic and are shared by the CLI and the dashboard.
- Money is always integer cents (`amount_cents`). Convert only at the edges with `money.parse_amount` / `money.format_amount`. Never use floats for money.
- User errors raise `IBudgetError` (from `ibudget.errors`); the CLI turns them into a red message and exit code 1. No stack traces for user mistakes.
- The dashboard is read-only and binds to `127.0.0.1` by default.

## Working rules

- Every change ships with tests. Tests use a temporary database (the `db_path` fixture); never touch the real one.
- Before saying a change is done: `.venv/bin/pytest` and `.venv/bin/ruff check .` must pass.
- When adding or changing a command, update the command table in `README.md`.
- After finishing a module, add an entry to `docs/ai-journal.md` (template at the top).
- Use the `add-ibudget-command` skill whenever adding or changing a CLI command.
- Agent skills live in `.agents/skills/<name>/SKILL.md`. Expose each one to Claude Code with a relative symlink: `ln -s ../../.agents/skills/<name> .claude/skills/<name>`.
- Commit in small steps with clear messages. Do not push unless asked.
