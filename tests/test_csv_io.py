import io
from pathlib import Path

import pytest

from ibudget.errors import IBudgetError
from ibudget.period import Month
from ibudget.repository import Repository
from ibudget.services.csv_io import ColumnMap, RowStatus, export_csv, import_csv

BANK = Path(__file__).parent / "fixtures" / "bank_sample.csv"
BANK_MAP = ColumnMap.parse("date=Booking date,amount=Amount,note=Description,category=Category")
BANK_OPTIONS = {"date_format": "%d.%m.%Y", "signed": True}


def write(tmp_path, text: str) -> Path:
    path = tmp_path / "input.csv"
    path.write_text(text, encoding="utf-8")
    return path


def test_column_map_parse():
    mapping = ColumnMap.parse(" date = Datum , Amount=Betrag")
    assert (mapping.date, mapping.amount, mapping.note) == ("Datum", "Betrag", "note")
    assert mapping.explicit == {"date", "amount"}
    assert ColumnMap.parse(None) == ColumnMap()


@pytest.mark.parametrize("text", ["date", "when=Datum", "date=", "date=Datum,,"])
def test_column_map_rejects_invalid(text):
    with pytest.raises(IBudgetError, match="Invalid --map entry"):
        ColumnMap.parse(text)


def test_import_bank_statement(repo):
    result = import_csv(repo, BANK, BANK_MAP, **BANK_OPTIONS)

    assert result.count(RowStatus.new) == 6
    assert result.count(RowStatus.income) == 1
    assert result.count(RowStatus.invalid) == 3
    invalid = {row.line: row.reason for row in result.rows if row.status is RowStatus.invalid}
    assert "not a valid amount" in invalid[9]
    assert "not a valid date" in invalid[10]
    assert invalid[11] == "zero amount"

    stored = {(e.note, e.amount_cents, e.category) for e in repo.list_expenses()}
    assert ("Rent November", 65000, "housing") in stored
    assert ("Monthly pass", 4500, "transport") in stored  # category matched case-insensitively
    assert ("New laptop", 123456, "other") in stored  # unknown category -> default
    # Two identical rows in one file are two real expenses, not duplicates.
    assert [e.note for e in repo.list_expenses()].count("Coffee") == 2


def test_reimport_skips_duplicates(repo):
    import_csv(repo, BANK, BANK_MAP, **BANK_OPTIONS)
    again = import_csv(repo, BANK, BANK_MAP, **BANK_OPTIONS)
    assert again.count(RowStatus.new) == 0
    assert again.count(RowStatus.duplicate) == 6
    assert len(repo.list_expenses()) == 6


def test_dry_run_changes_nothing(repo):
    result = import_csv(repo, BANK, BANK_MAP, dry_run=True, **BANK_OPTIONS)
    assert result.count(RowStatus.new) == 6
    assert repo.list_expenses() == []


def test_unsigned_import_takes_absolute_values(repo):
    import_csv(repo, BANK, BANK_MAP, date_format="%d.%m.%Y")
    salary = [e for e in repo.list_expenses() if e.note == "Salary"]
    assert salary[0].amount_cents == 250000


def test_default_columns_comma_file_and_custom_default_category(repo, tmp_path):
    path = write(
        tmp_path,
        'date,amount\n2026-11-01,"1,234.56"\n2026-11-02,7\n',  # no note or category columns
    )
    result = import_csv(repo, path, default_category="shopping")
    assert result.count(RowStatus.new) == 2
    assert {(e.amount_cents, e.category, e.note) for e in repo.list_expenses()} == {
        (123456, "shopping", ""),
        (700, "shopping", ""),
    }


def test_missing_columns(repo, tmp_path):
    path = write(tmp_path, "when,amount\n2026-11-01,5\n")
    with pytest.raises(IBudgetError, match="Column 'date' .* Columns in the file: when, amount"):
        import_csv(repo, path)
    path = write(tmp_path, "date,amount\n2026-11-01,5\n")
    with pytest.raises(IBudgetError, match="Column 'Text' \\(for note\\) not found"):
        import_csv(repo, path, ColumnMap.parse("note=Text"))


def test_bad_inputs(repo, tmp_path):
    with pytest.raises(IBudgetError, match="Cannot read"):
        import_csv(repo, tmp_path / "missing.csv")
    with pytest.raises(IBudgetError, match="is empty"):
        import_csv(repo, write(tmp_path, ""))
    with pytest.raises(IBudgetError, match="Unknown category 'pets'"):
        import_csv(repo, BANK, BANK_MAP, default_category="pets", **BANK_OPTIONS)


def test_export_round_trip(repo, add, tmp_path):
    add("2026-10-31", 999, "health", 'Pharmacy, "night"')
    add("2026-11-01", 65000, "housing", "Rent")
    add("2026-11-02", 1250, "food")

    out = io.StringIO()
    assert export_csv(repo, out, Month(2026, 11)) == 2
    lines = out.getvalue().splitlines()
    assert lines == [
        "id,date,amount,category,note",
        "2,2026-11-01,650.00,housing,Rent",
        "3,2026-11-02,12.50,food,",
    ]

    everything = io.StringIO()
    export_csv(repo, everything)
    path = write(tmp_path, everything.getvalue())
    fresh = Repository.open(tmp_path / "fresh.db")
    assert import_csv(fresh, path).count(RowStatus.new) == 3
    original = {(e.date, e.amount_cents, e.category, e.note) for e in repo.list_expenses()}
    copied = {(e.date, e.amount_cents, e.category, e.note) for e in fresh.list_expenses()}
    assert copied == original
    fresh.close()
