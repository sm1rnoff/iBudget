# AI journal

A running log of how AI assistants were used to build iBudget, one entry per module. It is the raw material for the exam write-up: what was asked, which tool, key prompts, what had to be corrected, and how the result was tested.

## Template

```
## <Module name> — <date>

- **Tool:** Claude Code (model) / Copilot / Cursor …, and why
- **Goal:** what this step had to deliver
- **Key prompts:**
  1. "…"
  2. "…"
- **What the AI produced:** files, commands, design decisions
- **What I corrected or rejected:** and why
- **Testing:** what tests were added, how the result was checked
```

---

## 0. Planning & requirements — 2026-11-02

- **Tool:** Claude Code (Opus 5.5) in the Claude desktop app, plan mode. Chosen because it can read the repo, ask clarifying questions and write the plan before touching code.
- **Goal:** pick a project, agree on scope, write requirements and an implementation plan.
- **Key prompts:**
  1. "First help me choose some simple project to implement. Propose some ideas.."
  2. "Honestly do you think it would be a good idea to add also an UI" → chose option B: a read-only web dashboard on top of the CLI.
  3. "We will go with option B. Let's write requirements and plan it first"
- **What the AI produced:** project ideas, the iBudget scope, `docs/requirements.md`, a step-by-step plan (one commit per module), the CLAUDE.md rules.
- **What I corrected or rejected:**
  - Python had been upgraded to 3.14, so the plan's uv-based Python install was not needed; after the AI explained what uv still adds, I chose plain `venv` + `pip`.
  - Categories had to support rename and delete, not only add.
  - Skills must live in `.agents/skills/` and be linked from `.claude/skills/`.
  - The dashboard must use HTMX instead of Chart.js.
- **Testing:** n/a (planning only).

## 1. Scaffold — 2026-11-02

- **Tool:** Claude Code (Opus 5.5), executing step 2 of the approved plan.
- **Goal:** an installable `ibudget` package with a `--version` command and a test/lint toolchain.
- **What the AI produced:** `pyproject.toml` (setuptools, `src/` layout, `ibudget` entry point, ruff and pytest config), a venv on Homebrew's `python3.14`, a smoke test.
- **What I corrected or rejected:** the AI noticed plain `python3` is still the system 3.9, so CLAUDE.md tells agents to always use `.venv/bin/...`.
- **Testing:** `ibudget --version`, `pytest` (1 test), `ruff check`.

## 2. Data layer — 2026-11-02

- **Tool:** Claude Code (Opus 5.5).
- **Goal:** SQLite schema, money and month helpers, and one repository class that holds every SQL query.
- **Key prompts:** "Implement step 3 of the plan: db.py, models.py, repository.py, money.py with tests."
- **What the AI produced:**
  - Schema with `PRAGMA user_version` for future migrations, seeded categories and currency.
  - Money as integer cents; `parse_amount` accepts `12.5`, `12,50`, `1.234,56` and `1,234.56`.
  - Category names unique case-insensitively (`COLLATE NOCASE`); budgets deleted with their category (`ON DELETE CASCADE`); the foreign key blocks deleting a category that still has expenses unless they are moved in the same transaction.
  - A `Month` value type (parse, shift, start/end) used by every layer.
- **What I corrected or rejected:** ruff flagged two over-long SQL lines; fixed.
- **Testing:** 36 new tests on a temporary database per test (an autouse fixture sets `IBUDGET_DB`, so real data is never touched).

## 3. CLI core — 2026-11-02

- **Tool:** Claude Code (Opus 5.5).
- **Goal:** `add`, `list`, `edit`, `delete`, full category management (add / rename / delete with reassign) and `config`.
- **Key prompts:**
  1. "Implement step 4 of the plan: CLI core with services for expenses, categories and config, and CliRunner tests."
  2. (from my plan review) "User must be able to add/delete and modify categories."
- **What the AI produced:**
  - Services `services/expenses.py`, `services/categories.py` and `config.py`; `cli.py` only parses input, calls them and prints Rich tables.
  - One `_session()` context manager in the CLI that opens the database and turns every `IBudgetError` into a red one-line message with exit code 1 — no stack traces for user mistakes.
  - Category deletion is split into `check_delete` (validate, no changes) and `delete`, so the CLI can show "moving 2 expense(s) to other" in the confirmation prompt *before* anything changes.
- **What I corrected or rejected:**
  - First version asked "Delete category?" and only then reported that the category still had expenses — fixed by validating before confirming.
  - ruff's B008 rule flagged Typer's `typer.Option(...)` defaults; configured them as allowed calls instead of rewriting the idiomatic Typer style.
  - A test assumed `list` shows `#1`; it shows a plain ID column — the test was wrong, not the code.
- **Testing:** 30 new tests (service-level for categories/config, end-to-end CLI tests through Typer's `CliRunner`, including a parametrized check that every user error exits 1 without a traceback). Manual run against a scratch database.

## 4. Budgets & reports — 2026-11-02

- **Tool:** Claude Code (Opus 5.5).
- **Goal:** monthly budgets per category, a warning after `add`, and a monthly report with shares, budget usage and change vs the previous month.
- **Key prompts:** "Implement step 5 of the plan: budgets and reports services, `budget` and `report` commands, warning after add, with tests for month boundaries, empty months and the previous-month comparison."
- **What the AI produced:** `services/budgets.py` (a `BudgetStatus` with ok / warning ≥ 90% / over levels), `services/reports.py` (`monthly_report` and a 6-month `trend` reused later by the dashboard), the `budget set|list|remove` and `report` commands.
- **What I corrected or rejected:**
  - The first `report` command decided the colour thresholds itself (`>= 90`), duplicating budget logic in the CLI. Moved into one `level_for()` function in the budgets service, used by both the budget list and the report.
  - A test expected "no data" for an empty month although a budget existed (budgets always show in the report). The behaviour was right; the test was split so the empty case runs on a fresh database.
- **Testing:** 19 new tests: exact level thresholds (26999 / 27000 / 30000 / 30001 cents for a 300 budget), month boundaries (1st and 30th in, 1st of next month out), a trend across a year boundary, CLI warnings. Manual `report` run.
