"""CSV import (bank statements) and export."""

import csv
import datetime as dt
import hashlib
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TextIO

from ibudget.errors import IBudgetError
from ibudget.money import parse_amount, plain_amount
from ibudget.period import Month, parse_date
from ibudget.repository import Repository
from ibudget.services import categories

EXPORT_COLUMNS = ("id", "date", "amount", "category", "note")
_FIELDS = ("date", "amount", "note", "category")
_REQUIRED = ("date", "amount")


@dataclass(frozen=True)
class ColumnMap:
    """Which CSV column holds each field. note and category are optional in the file."""

    date: str = "date"
    amount: str = "amount"
    note: str = "note"
    category: str = "category"
    explicit: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def parse(cls, text: str | None) -> ColumnMap:
        """'date=Booking date,amount=Amount' -> ColumnMap; unmapped fields keep their defaults."""
        if not text:
            return cls()
        values: dict[str, str] = {}
        for pair in text.split(","):
            key, sep, column = pair.partition("=")
            key = key.strip().lower()
            if not sep or key not in _FIELDS or not column.strip():
                raise IBudgetError(
                    f"Invalid --map entry '{pair}'. Use field=Column with fields "
                    f"{', '.join(_FIELDS)}, e.g. date=Datum,amount=Betrag."
                )
            values[key] = column.strip()
        return cls(**values, explicit=frozenset(values))


class RowStatus(StrEnum):
    new = "new"
    duplicate = "duplicate"
    invalid = "invalid"
    income = "income"  # positive amount skipped with --signed


@dataclass(frozen=True)
class ImportRow:
    line: int
    status: RowStatus
    date: dt.date | None = None
    amount_cents: int = 0
    category: str = ""
    note: str = ""
    reason: str = ""


@dataclass(frozen=True)
class ImportResult:
    rows: list[ImportRow]
    dry_run: bool

    def count(self, status: RowStatus) -> int:
        return sum(1 for row in self.rows if row.status is status)


def _row_hash(date: dt.date, cents: int, note: str, occurrence: int) -> str:
    # `occurrence` keeps identical rows in one file apart (two coffees on the same day),
    # while importing the same file again still produces the same hashes.
    key = f"{date.isoformat()}|{cents}|{note}|{occurrence}"
    return hashlib.sha256(key.encode()).hexdigest()


def _open_reader(handle: TextIO) -> csv.DictReader:
    # Pick the delimiter from the header line only: data rows may contain decimal commas
    # ("12,50"), which confuse csv.Sniffer in semicolon-separated bank exports.
    header = handle.readline()
    handle.seek(0)
    delimiter = max((";", "\t", ","), key=header.count)
    return csv.DictReader(handle, delimiter=delimiter)


def _resolve_columns(header: list[str], mapping: ColumnMap) -> dict[str, str | None]:
    """Field -> column name in this file (None for an absent optional column)."""
    present = {name.strip() for name in header}
    columns: dict[str, str | None] = {}
    for name in _FIELDS:
        column = getattr(mapping, name)
        if column in present:
            columns[name] = column
        elif name in _REQUIRED or name in mapping.explicit:
            raise IBudgetError(
                f"Column '{column}' (for {name}) not found. Columns in the file: "
                f"{', '.join(header)}. Use --map {name}=<column>."
            )
        else:
            columns[name] = None
    return columns


def import_csv(
    repo: Repository,
    path: Path,
    mapping: ColumnMap | None = None,
    *,
    date_format: str = "%Y-%m-%d",
    default_category: str = "other",
    signed: bool = False,
    dry_run: bool = False,
) -> ImportResult:
    """Import expenses from a CSV file.

    Amounts are taken as absolute values. With `signed`, the file follows bank conventions:
    negative amounts are expenses and positive ones (income) are skipped.
    Rows imported before (same date, amount, note and position among identical rows) are skipped
    as duplicates, so importing the same statement twice is safe.
    """
    mapping = mapping or ColumnMap()
    fallback = categories.require(repo, default_category)
    known = {c.name: c for c in repo.list_categories()}
    try:
        handle = path.open(newline="", encoding="utf-8-sig")
    except OSError as error:
        raise IBudgetError(f"Cannot read '{path}': {error.strerror}.") from None

    rows: list[ImportRow] = []
    new_rows: list[tuple[dt.date, int, int, str, str]] = []
    occurrences: Counter[tuple] = Counter()
    with handle:
        reader = _open_reader(handle)
        if not reader.fieldnames:
            raise IBudgetError(f"'{path}' is empty.")
        columns = _resolve_columns(reader.fieldnames, mapping)
        for record in reader:
            line = reader.line_num

            def value(name: str, record: dict = record) -> str:
                column = columns[name]
                return (record.get(column) or "").strip() if column else ""

            try:
                date = parse_date(value("date"), date_format)
                cents = parse_amount(value("amount"))
            except IBudgetError as error:
                rows.append(ImportRow(line, RowStatus.invalid, reason=str(error)))
                continue
            note = " ".join(value("note").split())
            if cents == 0:
                rows.append(
                    ImportRow(line, RowStatus.invalid, date, note=note, reason="zero amount")
                )
                continue
            if signed and cents > 0:
                rows.append(ImportRow(line, RowStatus.income, date, cents, note=note))
                continue
            cents = abs(cents)
            category = known.get(value("category").lower(), fallback)

            occurrences[(date, cents, note)] += 1
            import_hash = _row_hash(date, cents, note, occurrences[(date, cents, note)])
            if repo.import_hash_exists(import_hash):
                status = RowStatus.duplicate
            else:
                status = RowStatus.new
                new_rows.append((date, cents, category.id, note, import_hash))
            rows.append(ImportRow(line, status, date, cents, category.name, note))

    if not dry_run and new_rows:
        repo.add_imported(new_rows)
    return ImportResult(rows, dry_run)


def export_csv(repo: Repository, out: TextIO, month: Month | None = None) -> int:
    """Write expenses (oldest first) as CSV; the file can be imported again as-is."""
    found = repo.list_expenses(
        start=month.start if month else None, end=month.end if month else None
    )
    writer = csv.writer(out)
    writer.writerow(EXPORT_COLUMNS)
    for e in reversed(found):
        writer.writerow(
            [e.id, e.date.isoformat(), plain_amount(e.amount_cents), e.category, e.note]
        )
    return len(found)
