import datetime as dt
import sqlite3

import pytest

from ibudget.db import DEFAULT_CATEGORIES, SCHEMA_VERSION, default_db_path
from ibudget.repository import Repository


def test_new_database_is_seeded(repo):
    assert sorted(c.name for c in repo.list_categories()) == sorted(DEFAULT_CATEGORIES)
    assert repo.get_setting("currency") == "EUR"
    assert repo.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_reopening_does_not_reseed(db_path, repo):
    repo.add_category("pets")
    again = Repository.open(db_path)
    assert len(again.list_categories()) == len(DEFAULT_CATEGORIES) + 1
    again.close()


def test_default_db_path_uses_env(db_path):
    assert default_db_path() == db_path


def test_category_names_are_unique_case_insensitive(repo):
    assert repo.find_category("FOOD").name == "food"
    with pytest.raises(sqlite3.IntegrityError):
        repo.add_category("Food")


def test_rename_and_delete_category(repo, add):
    pets = repo.add_category("pets")
    add("2026-11-01", 900, "pets")
    repo.rename_category(pets.id, "pet-care")
    assert repo.get_expense(1).category == "pet-care"

    # Deleting a category that still has expenses is blocked by the foreign key...
    with pytest.raises(sqlite3.IntegrityError):
        repo.delete_category(pets.id)
    # ...unless its expenses are moved first, in the same transaction.
    other = repo.find_category("other")
    assert repo.delete_category(pets.id, reassign_to=other.id) == 1
    assert repo.get_expense(1).category == "other"
    assert repo.find_category("pet-care") is None


def test_add_get_update_delete_expense(repo, add):
    expense = add("2026-11-02", 1250, "food", "Lunch")
    assert expense.date == dt.date(2026, 11, 2)
    assert (expense.amount_cents, expense.category, expense.note) == (1250, "food", "Lunch")

    transport = repo.find_category("transport")
    repo.update_expense(expense.id, amount_cents=1400, category_id=transport.id)
    updated = repo.get_expense(expense.id)
    assert (updated.amount_cents, updated.category, updated.note) == (1400, "transport", "Lunch")

    repo.update_expense(expense.id)  # no changes is a no-op
    assert repo.delete_expense(expense.id) is True
    assert repo.delete_expense(expense.id) is False
    assert repo.get_expense(expense.id) is None


def test_amount_must_be_positive(repo):
    with pytest.raises(sqlite3.IntegrityError):
        repo.add_expense(dt.date(2026, 11, 1), 0, repo.find_category("food").id)


def test_list_expenses_filters_and_sorting(repo, add):
    add("2026-10-31", 500, "food")
    add("2026-11-01", 4500, "transport")
    add("2026-11-02", 1250, "food")
    add("2026-12-01", 800, "food")
    november = {"start": dt.date(2026, 11, 1), "end": dt.date(2026, 12, 1)}

    assert [e.amount_cents for e in repo.list_expenses(**november)] == [1250, 4500]
    assert [e.amount_cents for e in repo.list_expenses(**november, sort="amount")] == [4500, 1250]
    food = repo.find_category("food").id
    assert [e.amount_cents for e in repo.list_expenses(category_id=food)] == [800, 1250, 500]
    assert [e.amount_cents for e in repo.list_expenses(min_cents=800, max_cents=1250)] == [
        800,
        1250,
    ]
    assert len(repo.list_expenses(limit=2)) == 2


def test_totals(repo, add):
    add("2026-11-01", 4500, "transport")
    add("2026-11-02", 1250, "food")
    add("2026-11-30", 750, "food")
    add("2026-12-01", 800, "food")
    start, end = dt.date(2026, 11, 1), dt.date(2026, 12, 1)
    food = repo.find_category("food").id
    transport = repo.find_category("transport").id

    assert repo.totals_by_category(start, end) == {food: 2000, transport: 4500}
    assert repo.total_between(start, end) == 6500
    assert repo.total_between(start, end, food) == 2000
    assert repo.total_between(dt.date(2027, 1, 1), dt.date(2027, 2, 1)) == 0


def test_budgets(repo):
    food = repo.find_category("food")
    repo.set_budget(food.id, 30000)
    repo.set_budget(food.id, 25000)  # upsert
    assert repo.get_budget(food.id).limit_cents == 25000
    assert [(b.category, b.limit_cents) for b in repo.list_budgets()] == [("food", 25000)]
    assert repo.remove_budget(food.id) is True
    assert repo.remove_budget(food.id) is False
    assert repo.get_budget(food.id) is None


def test_budget_is_removed_with_its_category(repo):
    pets = repo.add_category("pets")
    repo.set_budget(pets.id, 5000)
    repo.delete_category(pets.id)
    assert repo.list_budgets() == []


def test_import_hash(repo):
    food = repo.find_category("food").id
    repo.add_expense(dt.date(2026, 11, 1), 100, food, import_hash="abc")
    assert repo.import_hash_exists("abc")
    assert not repo.import_hash_exists("xyz")


def test_settings(repo):
    assert repo.get_setting("missing", "fallback") == "fallback"
    repo.set_setting("currency", "BGN")
    assert repo.get_setting("currency") == "BGN"
