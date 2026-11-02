import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    id: int
    name: str


@dataclass(frozen=True)
class Expense:
    id: int
    date: dt.date
    amount_cents: int
    category_id: int
    category: str
    note: str
    import_hash: str | None = None


@dataclass(frozen=True)
class Budget:
    category_id: int
    category: str
    limit_cents: int
