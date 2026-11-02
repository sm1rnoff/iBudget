import pytest

from ibudget.errors import IBudgetError
from ibudget.period import Month
from ibudget.services import budgets
from ibudget.services.budgets import BudgetStatus, Level

NOV = Month(2026, 11)


@pytest.mark.parametrize(
    ("spent", "level"),
    [(0, Level.ok), (26999, Level.ok), (27000, Level.warning), (30000, Level.warning),
     (30001, Level.over)],
)  # fmt: skip
def test_levels(spent, level):
    assert BudgetStatus("food", 30000, spent).level is level


def test_status_numbers():
    status = BudgetStatus("food", 30000, 31250)
    assert (status.remaining_cents, status.percent) == (-1250, 104)


def test_set_list_remove(repo, add):
    add("2026-11-02", 28750, "food")
    add("2026-10-30", 5000, "food")  # previous month does not count
    budgets.set_budget(repo, "Food", "300")
    budgets.set_budget(repo, "transport", "100,50")

    statuses = {s.category: s for s in budgets.statuses(repo, NOV)}
    assert (statuses["food"].spent_cents, statuses["food"].level) == (28750, Level.warning)
    assert (statuses["transport"].limit_cents, statuses["transport"].spent_cents) == (10050, 0)

    budgets.remove(repo, "transport")
    assert [s.category for s in budgets.statuses(repo, NOV)] == ["food"]
    with pytest.raises(IBudgetError, match="has no budget"):
        budgets.remove(repo, "transport")


def test_status_for(repo, add):
    food = repo.find_category("food")
    assert budgets.status_for(repo, food.id, NOV) is None
    budgets.set_budget(repo, "food", "100")
    add("2026-11-02", 12000, "food")
    assert budgets.status_for(repo, food.id, NOV).level is Level.over


@pytest.mark.parametrize("amount", ["0", "-5", "abc"])
def test_set_budget_rejects_bad_amounts(repo, amount):
    with pytest.raises(IBudgetError):
        budgets.set_budget(repo, "food", amount)
