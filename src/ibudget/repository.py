"""All SQL lives here. Services call these methods; nothing else touches the database."""

import datetime as dt
import sqlite3
from pathlib import Path
from typing import Literal

from ibudget.db import connect
from ibudget.models import Budget, Category, Expense

ExpenseSort = Literal["date", "amount"]

_EXPENSE_SELECT = """
    SELECT e.id, e.date, e.amount_cents, e.category_id, c.name AS category, e.note, e.import_hash
    FROM expenses e JOIN categories c ON c.id = e.category_id
"""

_EXPENSE_ORDER = {
    "date": "e.date DESC, e.id DESC",
    "amount": "e.amount_cents DESC, e.date DESC, e.id DESC",
}


def _to_expense(row: sqlite3.Row) -> Expense:
    return Expense(
        id=row["id"],
        date=dt.date.fromisoformat(row["date"]),
        amount_cents=row["amount_cents"],
        category_id=row["category_id"],
        category=row["category"],
        note=row["note"],
        import_hash=row["import_hash"],
    )


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @classmethod
    def open(cls, path: Path | str | None = None) -> Repository:
        return cls(connect(path))

    def close(self) -> None:
        self.conn.close()

    # --- categories -------------------------------------------------------

    def list_categories(self) -> list[Category]:
        rows = self.conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
        return [Category(row["id"], row["name"]) for row in rows]

    def find_category(self, name: str) -> Category | None:
        sql = "SELECT id, name FROM categories WHERE name = ?"
        row = self.conn.execute(sql, (name,)).fetchone()
        return Category(row["id"], row["name"]) if row else None

    def add_category(self, name: str) -> Category:
        with self.conn:
            cursor = self.conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        return Category(cursor.lastrowid, name)

    def rename_category(self, category_id: int, name: str) -> None:
        with self.conn:
            self.conn.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))

    def delete_category(self, category_id: int, reassign_to: int | None = None) -> int:
        """Delete a category, first moving its expenses to `reassign_to` if given.

        Returns the number of moved expenses. Runs in one transaction.
        """
        with self.conn:
            moved = 0
            if reassign_to is not None:
                moved = self.conn.execute(
                    "UPDATE expenses SET category_id = ? WHERE category_id = ?",
                    (reassign_to, category_id),
                ).rowcount
            self.conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        return moved

    def count_expenses(self, category_id: int) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE category_id = ?", (category_id,)
        ).fetchone()[0]

    # --- expenses ---------------------------------------------------------

    def add_expense(
        self,
        date: dt.date,
        amount_cents: int,
        category_id: int,
        note: str = "",
        import_hash: str | None = None,
    ) -> Expense:
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO expenses (date, amount_cents, category_id, note, import_hash)"
                " VALUES (?, ?, ?, ?, ?)",
                (date.isoformat(), amount_cents, category_id, note, import_hash),
            )
        expense = self.get_expense(cursor.lastrowid)
        assert expense is not None
        return expense

    def get_expense(self, expense_id: int) -> Expense | None:
        row = self.conn.execute(f"{_EXPENSE_SELECT} WHERE e.id = ?", (expense_id,)).fetchone()
        return _to_expense(row) if row else None

    def list_expenses(
        self,
        *,
        start: dt.date | None = None,
        end: dt.date | None = None,
        category_id: int | None = None,
        min_cents: int | None = None,
        max_cents: int | None = None,
        sort: ExpenseSort = "date",
        limit: int | None = None,
    ) -> list[Expense]:
        """Expenses with `start <= date < end`, newest (or largest) first."""
        where, params = ["1 = 1"], []
        if start is not None:
            where.append("e.date >= ?")
            params.append(start.isoformat())
        if end is not None:
            where.append("e.date < ?")
            params.append(end.isoformat())
        if category_id is not None:
            where.append("e.category_id = ?")
            params.append(category_id)
        if min_cents is not None:
            where.append("e.amount_cents >= ?")
            params.append(min_cents)
        if max_cents is not None:
            where.append("e.amount_cents <= ?")
            params.append(max_cents)
        sql = f"{_EXPENSE_SELECT} WHERE {' AND '.join(where)} ORDER BY {_EXPENSE_ORDER[sort]}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [_to_expense(row) for row in self.conn.execute(sql, params).fetchall()]

    def update_expense(
        self,
        expense_id: int,
        *,
        date: dt.date | None = None,
        amount_cents: int | None = None,
        category_id: int | None = None,
        note: str | None = None,
    ) -> None:
        changes = {
            "date": date.isoformat() if date else None,
            "amount_cents": amount_cents,
            "category_id": category_id,
            "note": note,
        }
        changes = {column: value for column, value in changes.items() if value is not None}
        if not changes:
            return
        assignments = ", ".join(f"{column} = ?" for column in changes)
        with self.conn:
            self.conn.execute(
                f"UPDATE expenses SET {assignments} WHERE id = ?", [*changes.values(), expense_id]
            )

    def delete_expense(self, expense_id: int) -> bool:
        with self.conn:
            cursor = self.conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        return cursor.rowcount > 0

    def import_hash_exists(self, import_hash: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM expenses WHERE import_hash = ?", (import_hash,))
        return row.fetchone() is not None

    def totals_by_category(self, start: dt.date, end: dt.date) -> dict[int, int]:
        """Sum of amounts per category id for `start <= date < end`."""
        rows = self.conn.execute(
            "SELECT category_id, SUM(amount_cents) AS total FROM expenses"
            " WHERE date >= ? AND date < ? GROUP BY category_id",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return {row["category_id"]: row["total"] for row in rows}

    def total_between(self, start: dt.date, end: dt.date, category_id: int | None = None) -> int:
        sql = "SELECT COALESCE(SUM(amount_cents), 0) FROM expenses WHERE date >= ? AND date < ?"
        params: list = [start.isoformat(), end.isoformat()]
        if category_id is not None:
            sql += " AND category_id = ?"
            params.append(category_id)
        return self.conn.execute(sql, params).fetchone()[0]

    # --- budgets ----------------------------------------------------------

    def set_budget(self, category_id: int, limit_cents: int) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO budgets (category_id, monthly_limit_cents) VALUES (?, ?)"
                " ON CONFLICT (category_id)"
                " DO UPDATE SET monthly_limit_cents = excluded.monthly_limit_cents",
                (category_id, limit_cents),
            )

    def get_budget(self, category_id: int) -> Budget | None:
        row = self.conn.execute(
            "SELECT b.category_id, c.name, b.monthly_limit_cents FROM budgets b"
            " JOIN categories c ON c.id = b.category_id WHERE b.category_id = ?",
            (category_id,),
        ).fetchone()
        return Budget(row[0], row[1], row[2]) if row else None

    def list_budgets(self) -> list[Budget]:
        rows = self.conn.execute(
            "SELECT b.category_id, c.name, b.monthly_limit_cents FROM budgets b"
            " JOIN categories c ON c.id = b.category_id ORDER BY c.name"
        ).fetchall()
        return [Budget(row[0], row[1], row[2]) for row in rows]

    def remove_budget(self, category_id: int) -> bool:
        with self.conn:
            cursor = self.conn.execute("DELETE FROM budgets WHERE category_id = ?", (category_id,))
        return cursor.rowcount > 0

    # --- settings ---------------------------------------------------------

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)"
                " ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
