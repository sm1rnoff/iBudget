---
name: write-ibudget-tests
description: Writes, extends or fixes pytest tests the iBudget way — the right test file and fixture for each layer (repository, services, CLI, web routes, HTMX browser tests), a temporary database, fixed dates, integer cents, and a check that every new test can actually fail. Use whenever the user asks to add or improve tests in iBudget, reproduce a bug with a test, raise coverage, or fix a failing or flaky test, and whenever a change to src/ibudget needs its tests, even if they don't say "pytest".
---

# Writing iBudget tests

Every change in this repo ships with tests, and `.venv/bin/pytest` plus ruff must pass before anything is called done (`CLAUDE.md`). This skill keeps new tests consistent with the existing suite: same fixtures, same split between layers, same style. When adding or changing a CLI command, the `add-ibudget-command` skill says what to build; this one says how to test it.

## 1. Pick the layer, then the file

Test a rule at the lowest layer that owns it, and only the wiring in the layers above. A budget threshold is tested in the budgets service; the CLI and web tests only check that the result reaches the user. That keeps each failure pointing at one place.

| What changed | Test in | Use | Assert on |
|---|---|---|---|
| SQL in `repository.py`, schema in `db.py` | `tests/test_repository.py` | `repo`, `db_path` | returned models; `sqlite3.IntegrityError` for constraints |
| `money.py`, `period.py` | `tests/test_money.py` | plain calls, `parametrize` | exact cents (`1250`), `Month` values |
| `services/<area>.py`, `config.py` | `tests/test_<area>.py` (config tests live in `test_categories.py`) | `repo`, `add` | cents and dataclass fields; `pytest.raises(IBudgetError, match=...)` |
| `cli.py` | `tests/test_cli.py` | `run(...)` | `exit_code`, formatted output such as `"12.50 EUR"` |
| `web/app.py`, templates | `tests/test_web.py` | `client`, `november` | status code, HTML substrings, `HX-Push-Url` header |
| what HTMX swaps, where, or the URL it pushes | `tests/test_browser.py` | `dashboard`, `server_url` | see section 4 |

`services/expenses.py` has no test file of its own yet; the CLI and web tests cover it. Create `tests/test_expenses.py` when you add logic there that deserves direct tests.

## 2. Test data: temporary database, fixed dates, cents

- The autouse `db_path` fixture in `tests/conftest.py` gives every test a fresh database and points `IBUDGET_DB` at it, so the CLI and `default_db_path()` use it too. Never open or pass any other path; the real database must stay untouched.
- Insert expenses with `add("2026-11-14", 1250, "food", "Lunch")`: date, cents, category name, note. Seeded categories (`food`, `transport`, `housing`, ...) exist from the start; create others with `repo.add_category`.
- Use fixed dates around November 2026 (`NOV = Month(2026, 11)`), not today, so a test gives the same result next month. Only tests about "defaults to today" use `dt.date.today()` or `Month.current()`.
- Money is integer cents in services (`28750`) and formatted text at the edges (`"287.50"`). Never compare money as floats.
- Choose data that makes the assertion prove something: an expense in the previous month that must *not* count, a total that differs from every single row, and rows whose date order and amount order differ when testing sorting.
- An explicit input must differ from the default the code would fall back to, or the test cannot tell the input was used. Dates are the easy one to miss: when code defaults to today, pass a date that cannot be today, such as one in another year (`dt.date(2025, 3, 14)`). A date from the current month passes even when the argument is ignored, on the day the two happen to match.
- CSV input: build small files inline with the `write(tmp_path, text)` helper in `test_csv_io.py`. The shared bank sample is `tests/fixtures/bank_sample.csv`; reference it through `Path(__file__).parent`, not a path relative to the working directory.

## 3. Shape of a test

- One behaviour per test, named after it: `test_percent_rounds_down_to_match_level`, not `test_budgets_2`.
- Put edge cases in `@pytest.mark.parametrize` and test both sides of every threshold. Example: on a 300.00 budget, 26999 is ok, 27000 is a warning (90%), 30000 is still a warning and 30001 is over.
- When a number is not obvious, add a short comment saying why it matters, e.g. `# 98.85 of 110.00 is 89.86%: not yet a warning`.
- CLI checks: `assert result.exit_code == 0, result.output`, so a failure shows what the command printed.
- User errors:
  - services: `pytest.raises(IBudgetError, match="Unknown category 'pets'")`
  - CLI: add a row to `test_user_errors_exit_1_without_traceback` (exit code 1, the message, no `Traceback`)
  - web: add a row to `test_bad_requests` (400 for an `IBudgetError`, 422 for FastAPI validation)
- A bug fix starts with a test that reproduces the bug and fails. Then fix the code.
- Fake external effects with `monkeypatch` (see `test_serve_starts_uvicorn_on_localhost`). Apart from the browser tests loading HTMX, tests never use the network.

## 4. Browser tests (HTMX)

`tests/test_browser.py` runs the dashboard with uvicorn in a background thread and drives headless Chromium through pytest-playwright. `test_web.py` already proves what each route returns, so a browser test only proves the wiring: a user action sends the right request, and the response lands in the right place.

- **Data:** the server is session-scoped and reads its own database, seeded from the `EXPENSES` list at the top of the file. `repo` and `add` write to the per-test database, which the server never sees. Add rows to `EXPENSES` instead, then run the whole file, because existing tests assert exact lists of rows.
- **Start** from the `dashboard` fixture: November 2026, HTMX loaded, and a `window.notReloaded` marker set.
- **End** every test that triggers a swap with `assert_not_reloaded(page)`. A link that falls back to a full page load still shows the right content; only the marker catches it.
- **Locate** elements the way a user does: `get_by_role("navigation", name="Month")`, `get_by_label("Category")`, `get_by_title(...)`. Add a `data-testid` to a template only when no role, label or text identifies the element.
- **Assert** with `expect(...)`, which retries until the swap lands. Do not sleep (`wait_for_timeout`) or read text once.
- **Between interactions**, call `wait_until_settled(page)` after checking the swapped-in content and before using it. HTMX wires up new elements (such as the re-rendered filter form) about 20 ms after the swap, and acting sooner silently does nothing. This caused the first flaky failure in this suite.
- **Check what the user sees:** the new content, `to_have_url(...)` for the pushed URL, and `to_have_title(...)` when the month changes.
- **Debug** with `.venv/bin/pytest tests/test_browser.py --headed --slowmo 500`.

## 5. Prove the test can fail

A test that already passed before the change proves nothing. Before calling the work done:

- New behaviour: run the new test before the implementation (or with it stubbed) and see it fail for the right reason.
- Bug fix: the test fails on the old code.
- Test for existing code: break the code on purpose (flip a condition, change a threshold, remove an `hx-get`), see the test fail, then restore it with `git checkout -- <file>` and confirm `git status` shows the file clean.

Say in your summary what you broke and that the test caught it.

## 6. Run and report

```bash
.venv/bin/pytest tests/test_<area>.py           # while iterating on one file
.venv/bin/pytest --cov=ibudget                  # everything; coverage must stay at least 85% (NFR7)
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

- Browser tests need Chromium (`.venv/bin/playwright install chromium`) and network access for HTMX's CDN. If they cannot run, run `-m "not browser"` and say so; never report the full suite as green when part of it was skipped.
- Run a new or changed browser test file 3–5 times in a row. A test that passes once and fails once is worse than no test.
- Report honestly: tests passed, coverage, anything skipped, and what the "prove it can fail" check showed.
