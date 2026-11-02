"""SQLite connection and schema."""

import os
import sqlite3
from pathlib import Path

from platformdirs import user_data_path

DEFAULT_CATEGORIES = (
    "food",
    "transport",
    "housing",
    "utilities",
    "health",
    "entertainment",
    "shopping",
    "other",
)
DEFAULT_CURRENCY = "EUR"
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE categories (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);
CREATE TABLE expenses (
    id           INTEGER PRIMARY KEY,
    date         TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    category_id  INTEGER NOT NULL REFERENCES categories(id),
    note         TEXT NOT NULL DEFAULT '',
    import_hash  TEXT UNIQUE,
    created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX expenses_date ON expenses(date);
CREATE INDEX expenses_category ON expenses(category_id);
CREATE TABLE budgets (
    category_id         INTEGER PRIMARY KEY REFERENCES categories(id) ON DELETE CASCADE,
    monthly_limit_cents INTEGER NOT NULL CHECK (monthly_limit_cents > 0)
);
CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def default_db_path() -> Path:
    """`IBUDGET_DB` if set, otherwise the platform's user data directory."""
    if env := os.environ.get("IBUDGET_DB"):
        return Path(env).expanduser()
    return user_data_path("ibudget") / "ibudget.db"


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open the database, creating and seeding it on first use."""
    db_path = Path(path).expanduser() if path else default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Each connection is used by one CLI run or one web request, possibly from a worker thread.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version >= SCHEMA_VERSION:
        return
    conn.executescript(f"BEGIN;\n{SCHEMA}\n")
    try:
        conn.executemany(
            "INSERT INTO categories (name) VALUES (?)", [(name,) for name in DEFAULT_CATEGORIES]
        )
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('currency', ?)", (DEFAULT_CURRENCY,)
        )
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
