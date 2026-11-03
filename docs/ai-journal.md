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

## 5. CSV import/export — 2026-11-02

- **Tool:** Claude Code (Opus 5.5).
- **Goal:** import bank statements safely (preview, duplicates, bad rows) and export to CSV.
- **Key prompts:** "Implement step 6 of the plan: CSV import with column mapping, date formats, comma decimals, duplicate detection and dry-run, plus export, tested with a sample bank CSV."
- **What the AI produced:** `services/csv_io.py` (`ColumnMap`, `import_csv`, `export_csv`), `import` / `export` commands with a dry-run preview table, `tests/fixtures/bank_sample.csv` (semicolon-separated, `dd.mm.yyyy` dates, `1.234,56` amounts, an income row and three broken rows).
- **What I corrected or rejected:**
  - The plan said "take absolute values". While writing the fixture the AI noticed that a salary row would then be imported as an expense, and added a `--signed` option (bank convention: negative = expense, positive rows skipped as income).
  - The plan's duplicate key `sha256(date|amount|note)` would merge two genuine identical rows (two coffees on the same day). The key now also includes the row's occurrence number among identical rows in the file, so re-importing is still idempotent.
  - `csv.Sniffer` can mistake decimal commas (`12,50`) for the delimiter in semicolon files, so the delimiter is now picked from the header line only.
  - One CLI test had a wrong hand-calculated total (1,945.46 instead of 1,948.46) — the test was fixed, the code was right.
- **Testing:** 16 new tests, including the fixture end to end, re-import = all duplicates, dry run writes nothing, missing/explicitly mapped columns, and an export → import round trip into a fresh database (with commas and quotes in notes).

## 6. HTMX dashboard — 2026-11-02

- **Tool:** Claude Code (Opus 5.5), plus its built-in browser to check the running page.
- **Goal:** `ibudget serve` — a read-only dashboard that reuses the CLI's services and updates in place with HTMX.
- **Key prompts:**
  1. (from my plan review) "For UI choose HTMX."
  2. "Implement step 7 of the plan: FastAPI app, Jinja2 templates and partials, CSS bars, serve command, TestClient tests."
- **What the AI produced:**
  - `web/app.py` with three routes: `/` (full page), `/partials/month` (everything for one month) and `/partials/expenses` (just the table). Each partial response sets an `HX-Push-Url` header, so the address bar always shows the shareable full-page URL and the back button works.
  - Server-rendered HTML/CSS bars instead of a chart library, so swapped fragments need no JavaScript besides HTMX. Links and the filter form also work without JavaScript (progressive enhancement).
  - `demo/expenses.csv` + `demo/setup.sh` for reproducible screenshots.
- **What I corrected or rejected (found while checking the page in the browser):**
  - Utilities showed "90%" in green with "0 near budget": 98.85 / 110 is 89.86%, which was rounded up for display while the warning starts at 90%. Budget percentages now round down; regression test added.
  - The browser tab title stayed on the old month after an HTMX swap; the month partial now includes a `<title>` that HTMX applies.
  - Mobile: doubled spacing between cards and cramped month buttons (now "‹ Oct" / "Dec ›").
  - ruff flagged `Depends(...)` defaults; switched to FastAPI's recommended `Annotated[..., Depends(...)]` style.
  - Starlette deprecated `httpx` for its test client; the dev dependency is now `httpx2`.
- **Testing:** 14 web tests with FastAPI's `TestClient` (full page, fragments, `HX-Push-Url`, filters, sorting, empty month, 400/422 errors, read-only `POST` → 405, HTML escaping). In the browser: filter, month switch and back button verified without a full reload (a JS marker survived), no console errors, mobile and light/dark layouts.

## 7. Project skill, polish & evidence — 2026-11-02

- **Tool:** Claude Code (Opus 5.5).
- **Goal:** capture the project's way of working as a reusable agent skill, and collect evidence that the system works.
- **Key prompts:**
  1. (from my plan review) "All skills must be stored under .agents/skills folder and referred by shortcuts from .claude/skills folder."
  2. "Implement step 8 of the plan: the add-ibudget-command skill, README usage, demo data and screenshots."
- **What the AI produced:**
  - `.agents/skills/add-ibudget-command/SKILL.md` — the checklist used throughout this project (where logic goes, a command template, which tests, which docs), exposed to Claude Code through a relative symlink `.claude/skills/add-ibudget-command`.
  - A test for `ibudget serve` (uvicorn mocked), bringing coverage to 99%.
  - Screenshots in `docs/screenshots/`: the dashboard (dark; light with a filter applied) and a terminal capture of real `add` / `report` / `budget list` output, recorded with Rich against a copy of the demo database.
- **What I corrected or rejected:** the Claude desktop preview tool still read the previous project's `launch.json`, so the dashboard server was started from the shell for the browser checks instead of editing the other repository.
- **Testing:** 117 tests, 99% coverage, ruff clean; the plan's end-to-end CLI scenario run against a fresh database (add, category add/rename/delete with reassign, budget, import dry-run/import/re-import, list, report, export).

## 8. Browser tests — 2026-11-02

- **Tool:** Claude Code (Opus 5.5).
- **Goal:** test the dashboard's HTMX behaviour in a real browser, not only the HTML each route returns.
- **Key prompts:**
  1. "can I test htmx web site with cypress framework?" → yes, but the AI recommended pytest-playwright for this repo: same language, same `pytest` run, no Node toolchain.
  2. "Use Playwright"
- **What the AI produced:**
  - `tests/test_browser.py`: uvicorn serves the app from a seeded temporary database in a background thread (on a port the OS picks), and pytest-playwright drives headless Chromium.
  - Four tests: month link, trend bar, back button, category filter + sort. Each checks the swapped content, the pushed URL (and title), and a JS marker on `window` that a full reload would wipe out.
  - A `browser` pytest marker, so `pytest -m "not browser"` skips them offline (HTMX comes from the CDN).
- **What I corrected or rejected:** the first run of the filter-then-sort test failed: the Sort change right after the category swap sent no request. HTMX only wires up swapped-in elements (the re-rendered filter form) when it settles, ~20 ms after the swap, and Playwright was faster than that. Not a dashboard bug, so the tests now wait for the `htmx-settling` class to clear before the next interaction.
- **Testing:** 5 runs in a row green. Mutation check: removing `hx-get` from the previous-month link and switching the filter to `hx-trigger="submit"` made 3 of the 4 tests fail, as expected. Full suite: 121 tests, 99% coverage, ruff clean.

## 9. Testing skill — 2026-11-02

- **Tool:** Claude Code (Opus 5.5), with Anthropic's `skill-creator` skill for the structure and validation.
- **Goal:** a reusable skill so any agent writes tests that fit this suite instead of generic pytest.
- **Key prompts:**
  1. "is there a skill for pytest I could use ready and will fit my use-case?" → the AI searched the skill and plugin catalogs. There was no standalone pytest skill; py-pit's `pytest-service` comes bundled with skills for uv, SQLAlchemy, Alembic and Click, which this project does not use, and the Playwright plugins duplicate the browser tests already here.
  2. "Yes, write it"
- **What the AI produced:** `.agents/skills/write-ibudget-tests/SKILL.md`, linked from `.claude/skills/`: which layer and file to test in, test data rules (temporary database, fixed dates, cents, data that proves something), the shape of a test, the browser-test rules learned in step 8 (seed through `EXPENSES`, the reload marker, `wait_until_settled`), proving each test can fail, and how to report. `add-ibudget-command` now points to it for its testing step.
- **What I corrected or rejected:** nothing yet. The skill-creator's with/without-skill benchmark was not run, so the skill is checked by validation only.
- **Testing:** skill-creator's `quick_validate` passes; a script confirmed that all 30 fixtures, helpers, test names and paths the skill cites exist; Claude Code listed the skill as soon as it was linked. Suite unchanged: 121 tests, ruff clean.

## 10. Benchmarking the testing skill — 2026-11-02

- **Tool:** Claude Code (Opus 5.5) with Anthropic's `skill-creator`: subagents ran each task with and without the skill, each in its own clone of the repo with its own venv; the baseline clones had the pre-skill repo (no skill, no CLAUDE.md rule, no journal entry 9).
- **Goal:** find out whether `write-ibudget-tests` actually makes an agent write better tests here.
- **Key prompts:**
  1. "Run the benchmark"
  2. "Fix, rerun on Sonnet"
- **What the AI produced:** three test cases in `.agents/skills/write-ibudget-tests/evals/` (tests for the expenses service; a browser test for the transport filter; a "last day of the month goes missing" bug report that is not a bug), 22 graded statements, grading scripts that re-ran each copy's suite and planted known bugs, and skill-creator's review page.

  | Iteration | Agent model | With skill | Without skill | Time / tokens with skill |
  |---|---|---|---|---|
  | 1 | Opus 5.5 | 96% (21/22) | 100% | +25 s, +6.7k |
  | 2 (fixed skill) | Sonnet 5.5 | 100% | 100% | −7 s, −2.8k |

- **What I corrected or rejected:**
  - Iteration 1 found a flaw in the skill itself: its example date and its "fixed dates around November 2026" advice matched the day of the run, so the with-skill agent's "explicit date" test could not notice `expenses.add` ignoring its date argument. The baseline had pinned today and caught it. The skill now says explicit inputs must differ from the default the code falls back to; in iteration 2 the with-skill agent used a 2025 date and the planted bug was caught.
  - The honest result: both models already pass every check without the skill, because CLAUDE.md, the conftest fixtures and the documented browser helpers carry the conventions. The skill's measurable effect is small (one fixed blind spot, a lighter-touch browser seed change). Showing a real benefit would need harder cases where the code does not already demonstrate the pattern.
- **Testing:** one run per configuration and case (12 agent runs). The grader re-ran every copy's full suite, ruff, the browser tests 3 times, and planted bugs (an ignored date argument, `<` → `<=` on month ends) against each run's new tests.

## 11. Schema-change skill — 2026-11-03

- **Tool:** Claude Code (Opus 5.5) with Anthropic's `skill-creator`; the benchmark ran each task with and without the skill, in separate clones with their own venvs.
- **Goal:** a skill for the one change this codebase does not teach: altering the database schema without breaking users' existing files.
- **Key prompts:**
  1. "can you suggest other skills which may eventually improve the way you write and build this app?" → the AI ranked candidates by what the code does *not* already show; `db._migrate` only knows how to create a new database, and every test starts from an empty one.
  2. "Yes, write it"
- **What the AI produced:**
  - `.agents/skills/change-ibudget-schema/SKILL.md`: when a schema change is needed at all (settings and computed values need none), freezing the current version as `tests/fixtures/schema_vN.sql`, append-only migration steps with one transaction each, a backup (`<file>.vN.bak`) before upgrading, SQLite limits (`executescript` commits, `ADD COLUMN` restrictions, `PRAGMA foreign_keys` ignored in a transaction), following new data through the app, and the upgrade tests.
  - Before publishing, every SQLite claim was checked on Python 3.14 / SQLite 3.54. The skill's template was applied literally in a scratch clone: 122 tests passed, the demo database upgraded with a backup, and a newer file was refused with exit code 1.
  - Three eval cases in `evals/`: a recurring flag (new column), monthly income (new table) and a trend-months setting (should need no schema change).
- **What I corrected or rejected:** nothing in the skill. Benchmark result: 17/17 checks with and without the skill. Two caveats:
  - The baseline was not clean. Subagents inherit the session's skill list, so the baseline agents saw the skill's one-line description, which already names versioned steps and a frozen dump.
  - Ungraded differences went the skill's way. Only the with-skill runs back up the database before upgrading and refuse a database from a newer version, and they wrote more upgrade tests.
- **Testing:** a checker restored a pristine version-1 demo database (140 expenses, 9 categories, 4 budgets) for every run. It then ran that run's code on it, compared the schema with a new database, and tried the new feature. The real database's fingerprint was unchanged afterwards.
- **Clean rerun** ("Rerun them"): the three baselines were run again with the skill fully hidden.
  - **How it was hidden:** the skill link and the CLAUDE.md rule were removed for the duration of the runs. The copies started from the commit before the skill, with later history pruned, and got the same prompt as the with-skill runs. Only the skill's *name* could still be seen, in the session's list of recent commit titles.
  - **Result:** 17/17 again. Without the skill, Opus still found the trap in all three tasks. It wrote versioned steps in one transaction and upgrade tests with data, and it left the schema alone for the setting.
  - **What only the skill produced:**
    - a backup before upgrading (with skill 2/2, without 0/2);
    - a refusal of databases from a newer version (2/2 vs 0/2);
    - upgrade tests that start from a dump made by the old code. One clean baseline froze the schema inside its test. The other rebuilt it from the new code's constant, which would follow a later accidental edit.
  - **Conclusion:** the skill doesn't make the difference between a working and a broken migration on Opus. It does make migrations safer and more uniform.

## 12. Subagents per layer — 2026-11-03

- **Tool:** Claude Code (Opus 5.5).
- **Goal:** split the work between two specialised subagents, with the main agent routing tasks and handling the cases that span both.
- **Key prompts:** "I want you to define a couple of sub-agents to share the work one for htmx related tasks and one for the python code. When there's a task related to both - you decide who and how to handle it"
- **What the AI produced:**
  - `.claude/agents/htmx-dashboard.md`: owns `web/` (routes, templates, partials, CSS) and the web and browser tests. It describes the HTMX conventions this app relies on: `HX-Push-Url` via `page_url()`, the `<title>` in the month partial, links and forms that also work without JavaScript, GET only, the ~20 ms settle, and visual checks at 375 and 320 px in light and dark mode. It preloads `write-ibudget-tests`.
  - `.claude/agents/python-core.md`: owns everything in `src/ibudget/` outside `web/` and the remaining tests. It preloads `write-ibudget-tests` and `add-ibudget-command`, loads `change-ibudget-schema` before any schema change, and lists the service functions the dashboard depends on, so their contracts don't break unannounced.
  - Both run with the session's model, can't spawn their own subagents, don't commit, and report a precise contract whenever they need something from the other side.
  - CLAUDE.md "Subagents": an ownership table and routing rules. Small changes are done directly. One-sided tasks go to that agent. Tasks that touch both are split at the service boundary, with the contract written into both briefs: `python-core` goes first, then `htmx-dashboard` with its report. They run in parallel only when the halves are independent, each in its own worktree. The main agent reviews, writes the journal and commits.
- **What I corrected or rejected:** agent files live directly in `.claude/agents/`, not in `.agents/` behind symlinks like the skills. The agent format is specific to Claude Code, and its docs don't say whether symlinked agent files are picked up.
- **Testing:** the frontmatter was parsed and checked against the documented fields, and every preloaded skill exists. A script assigned all 38 files in `src/` and `tests/` to exactly one agent. The agents become available after a session restart, because `.claude/agents/` didn't exist when this session started.
- **Follow-up, moved to `.agents/agents/`:** the user asked whether agents can live under `.agents/` like the skills. The docs don't cover symlinks, so the AI tested it with the Claude Code 2.1.309 binary in scratch repos, using a probe agent that only replies with a fixed word. A per-file symlink and a symlinked folder both loaded the agent; an unknown name was refused. The two agents now live in `.agents/agents/`, with one symlink per file in `.claude/agents/`, and CLAUDE.md has the matching rule. One thing is untested: whether an edit to a symlinked agent is picked up without restarting the session.
