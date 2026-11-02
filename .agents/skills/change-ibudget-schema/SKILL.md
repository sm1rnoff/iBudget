---
name: change-ibudget-schema
description: Changes the iBudget SQLite schema without breaking existing users' databases — append-only versioned migration steps in db.py, a backup before upgrading, and an upgrade test from a frozen dump of the previous version. Use whenever a change needs a new table, column, index, constraint or seed data, touches db.py, SCHEMA or SCHEMA_VERSION, or a feature has to store something new (recurring expenses, income, tags, ...), even if the user never mentions the database or migrations.
---

# Changing the iBudget database schema

Every CLI command and every dashboard request opens the user's database through `db.connect`, which calls `_migrate`. So a user who installs a new ibudget runs the new code against their existing file, and that file is the only copy of their finances.

The test suite cannot see the risk: every test starts from an empty database. A change that only works for new databases passes every test, then breaks every command for existing users. For example, if you edit `SCHEMA` and bump `SCHEMA_VERSION` to 2, `_migrate` reruns the whole version-1 script on an existing file. The result is `OperationalError: table categories already exists`, shown as a stack trace on every command.

## 1. Check that you need a schema change

- **A new user preference:** no schema change. Add a key to `SETTINGS` and `DEFAULTS` in `config.py`; the `settings` table is key/value.
- **A value you can compute from existing data:** no schema change. Compute it in a service.
- **An existing but unused column:** `expenses.created_at` is filled in by SQLite on insert but isn't in the `Expense` model. Expose it through `_EXPENSE_SELECT` and `_to_expense` rather than adding a column.
- **A new fact to store** (a flag on expenses, income per month, tags): yes. Continue.

## 2. Before you edit anything, freeze the current version

The upgrade test needs a database exactly as the current release writes it, so create it with the code as it is *before* your change. Skip this step if `tests/fixtures/schema_v<N>.sql` already exists for the current version.

```bash
V=$(.venv/bin/python -c "from ibudget.db import SCHEMA_VERSION; print(SCHEMA_VERSION)")
D=$(mktemp -d)
IBUDGET_DB=$D/old.db .venv/bin/ibudget category add pets
IBUDGET_DB=$D/old.db .venv/bin/ibudget add 12.50 food Lunch --date 2026-11-14
IBUDGET_DB=$D/old.db .venv/bin/ibudget add 40 pets Vet --date 2026-10-03
IBUDGET_DB=$D/old.db .venv/bin/ibudget budget set food 300
.venv/bin/python -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print('\n'.join(c.iterdump())); print(f'PRAGMA user_version = {sys.argv[2]};')" $D/old.db $V > tests/fixtures/schema_v$V.sql
```

`iterdump` doesn't save `user_version`, which is why the script appends that last line. Commit the fixture and never edit it: it is what users have on disk. If you also want a realistic database to try by hand (section 7), run `./demo/setup.sh` now, before the change. It writes `.demo/ibudget.db`, which is gitignored.

## 3. Turn `_migrate` into steps (first schema change only)

Today `_migrate` knows only one move: from an empty database to version 1. On the first schema change, replace it with a list of steps, where `MIGRATIONS[i]` upgrades a database from version i to i + 1. New databases run every step from 0, so new and upgraded databases end up identical by construction.

```python
SCHEMA_V1 = """..."""  # the former SCHEMA, unchanged


def _create_v1(conn: sqlite3.Connection) -> None:
    """Version 1 as first released: tables, default categories, currency."""
    for statement in SCHEMA_V1.split(";"):
        if statement.strip():
            conn.execute(statement)
    conn.executemany(
        "INSERT INTO categories (name) VALUES (?)", [(name,) for name in DEFAULT_CATEGORIES]
    )
    conn.execute("INSERT INTO settings (key, value) VALUES ('currency', ?)", (DEFAULT_CURRENCY,))


def _add_recurring(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE expenses ADD COLUMN recurring INTEGER NOT NULL DEFAULT 0")


# MIGRATIONS[i] upgrades a database from version i to i + 1. Append only: released steps
# made the files users have, so a mistake is fixed by a new step, never by editing an old one.
MIGRATIONS = (_create_v1, _add_recurring)
SCHEMA_VERSION = len(MIGRATIONS)


def _migrate(conn: sqlite3.Connection, db_path: Path) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise IBudgetError(
            f"{db_path} was created by a newer ibudget (schema {version}); upgrade ibudget."
        )
    if 0 < version < SCHEMA_VERSION:  # an existing database is about to change
        with sqlite3.connect(db_path.with_name(f"{db_path.name}.v{version}.bak")) as backup:
            conn.backup(backup)
    for target, step in enumerate(MIGRATIONS[version:], start=version + 1):
        conn.execute("BEGIN")
        try:
            step(conn)
            conn.execute(f"PRAGMA user_version = {target}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
```

- Keep the `SCHEMA_VERSION` name, because tests import it. `connect` now passes `db_path` to `_migrate`.
- Each step and its version number commit together, or not at all. A failed upgrade leaves the file at the old version, with the backup next to it.
- The backup (`ibudget.db.v1.bak`) is a product behaviour the user will see. Say so in your summary.

## 4. Write the step: SQLite rules

- **One statement at a time:** run every statement with `conn.execute`. Never use `executescript` inside a step: it commits the open transaction first, so a failure would leave half a migration with the new version number.
- **`ALTER TABLE ... ADD COLUMN`** covers most changes. A NOT NULL column needs a constant default (`INTEGER NOT NULL DEFAULT 0`). It cannot be UNIQUE or a PRIMARY KEY, and cannot default to `CURRENT_TIMESTAMP`; if you need a computed value, add the column with a constant default and fill it with an `UPDATE` in the same step. CHECK constraints are allowed.
- **Types:** booleans are `INTEGER` 0/1 with `CHECK (x IN (0, 1))`, money is `INTEGER` cents, dates are `TEXT` `YYYY-MM-DD`, and months are `TEXT` `YYYY-MM`. Never use REAL for money.
- **New tables:** use plain `CREATE TABLE`, not `IF NOT EXISTS`. The version number already guarantees a step runs once, and `IF NOT EXISTS` would hide a wrong version. Seed data for a new table goes in its step. Never insert `DEFAULT_CATEGORIES` again.
- **`RENAME COLUMN` and `DROP COLUMN`** work, but you can't drop a column that is indexed, UNIQUE or a foreign key. Any other change (a column's type or constraint) needs a table rebuild: create the new table, copy the rows, drop the old one, rename. If other tables reference the rebuilt one (`categories` is referenced by `expenses` and `budgets`, with `ON DELETE CASCADE`), dropping it with foreign keys on deletes budgets. `PRAGMA foreign_keys = OFF` is ignored inside a transaction, so stop and ask the user before a rebuild like that.

## 5. Follow the new data through the app

For a new `expenses` column, update each of these:
- the `Expense` model, with a default so existing constructors still work;
- `_EXPENSE_SELECT` and `_to_expense`;
- `Repository.add_expense` and `update_expense`;
- the service;
- the CLI, using the `add-ibudget-command` skill;
- the dashboard templates, if the data should show there;
- CSV `EXPORT_COLUMNS` and the import, if the value should survive an export and re-import.

All SQL stays in `repository.py`.

## 6. Tests

Put these in `tests/test_repository.py`, next to `test_new_database_is_seeded`. Follow `write-ibudget-tests` for everything else.

```python
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("old", sorted(FIXTURES.glob("schema_v*.sql")))
def test_upgrade_keeps_existing_data(db_path, old):
    conn = sqlite3.connect(db_path)
    conn.executescript(old.read_text())
    conn.close()

    repo = Repository.open(db_path)  # runs the migration
    assert repo.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert [e.note for e in repo.list_expenses()] == ["Lunch", "Vet"]
    assert len(repo.list_categories()) == len(DEFAULT_CATEGORIES) + 1  # pets; not seeded twice
    assert [b.limit_cents for b in repo.list_budgets()] == [30000]
    assert db_path.with_name(f"{db_path.name}.{old.stem.removeprefix('schema_')}.bak").exists()
    # ...and the new column or table, with its default on the old rows
```

Also add:
- **Same schema:** a new database and an upgraded one have identical `SELECT type, name, sql FROM sqlite_master ORDER BY type, name`.
- **Second open:** opening the upgraded file again changes nothing and writes no second backup.
- **Newer file:** `PRAGMA user_version = 99` gives a clean `IBudgetError`, and the CLI exits with 1 and no traceback.
- **Rollback:** if a step runs more than one statement, monkeypatch in a step that fails halfway, and check that the version and schema are unchanged afterwards.

## 7. Try it on a realistic old database

Copy `.demo/ibudget.db`, made before the change in section 2, and run the new code against the copy:

```bash
D=$(mktemp -d) && cp .demo/ibudget.db "$D/demo.db"
.venv/bin/ibudget --db "$D/demo.db" report && .venv/bin/ibudget --db "$D/demo.db" list --all
ls "$D"   # demo.db and demo.db.v1.bak
```

Run a command a second time, and use the new feature on the upgraded copy. Never point development code at the real database in the platform data directory.

## 8. Docs and report

- Add new stored data to `docs/requirements.md`, new or changed commands to the README command table, and an entry to `docs/ai-journal.md` that says "schema N → N+1".
- In your summary, give the version change and say that existing databases upgrade on their first use, keeping a backup at `<file>.vN.bak`. Also say how you checked it: the upgrade test, plus a copy of the demo database.
