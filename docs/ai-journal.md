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
