import pytest

from ibudget import config
from ibudget.errors import IBudgetError
from ibudget.services import categories


def test_add_normalizes_name(repo):
    assert categories.add(repo, "  Pet   Care ").name == "pet care"
    with pytest.raises(IBudgetError, match="already exists"):
        categories.add(repo, "PET CARE")


@pytest.mark.parametrize("name", ["", "   ", "-food", "a" * 31, "food/drinks"])
def test_add_rejects_invalid_names(repo, name):
    with pytest.raises(IBudgetError, match="not a valid category name"):
        categories.add(repo, name)


def test_require_lists_known_categories(repo):
    with pytest.raises(IBudgetError, match="Unknown category 'pets'. Known categories: "):
        categories.require(repo, "pets")


def test_rename_keeps_expenses_and_budget(repo, add):
    add("2026-11-01", 900, "food")
    repo.set_budget(repo.find_category("food").id, 30000)
    assert categories.rename(repo, "food", "Groceries").name == "groceries"
    assert repo.get_expense(1).category == "groceries"
    assert repo.list_budgets()[0].category == "groceries"


def test_rename_to_same_name_with_other_case_is_allowed(repo):
    assert categories.rename(repo, "food", "food").name == "food"


def test_rename_conflict(repo):
    with pytest.raises(IBudgetError, match="already exists"):
        categories.rename(repo, "food", "Transport")


def test_delete_unused_category(repo):
    categories.add(repo, "pets")
    deletion = categories.delete(repo, "pets")
    assert (deletion.category.name, deletion.expense_count) == ("pets", 0)
    assert repo.find_category("pets") is None


def test_delete_used_category_requires_reassign(repo, add):
    add("2026-11-01", 900, "food")
    add("2026-11-02", 100, "food")
    with pytest.raises(IBudgetError, match="has 2 expense"):
        categories.delete(repo, "food")
    with pytest.raises(IBudgetError, match="being deleted"):
        categories.delete(repo, "food", reassign_to="FOOD")
    with pytest.raises(IBudgetError, match="Unknown category"):
        categories.delete(repo, "food", reassign_to="nowhere")

    deletion = categories.delete(repo, "food", reassign_to="other")
    assert deletion.expense_count == 2
    assert {e.category for e in repo.list_expenses()} == {"other"}


def test_overview(repo, add):
    add("2026-11-01", 900, "food")
    repo.set_budget(repo.find_category("food").id, 30000)
    rows = {row.name: row for row in categories.overview(repo)}
    assert (rows["food"].expense_count, rows["food"].budget_cents) == (1, 30000)
    assert (rows["health"].expense_count, rows["health"].budget_cents) == (0, None)


def test_config(repo):
    assert config.currency(repo) == "EUR"
    assert config.set(repo, "currency", " bgn ") == "BGN"
    assert config.all_settings(repo) == {"currency": "BGN"}
    with pytest.raises(IBudgetError, match="three letters"):
        config.set(repo, "currency", "euro")
    with pytest.raises(IBudgetError, match="Unknown setting"):
        config.get(repo, "colour")
