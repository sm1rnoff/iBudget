from dataclasses import dataclass
from enum import StrEnum

from ibudget.errors import IBudgetError
from ibudget.models import Budget
from ibudget.money import parse_positive_amount
from ibudget.period import Month
from ibudget.repository import Repository
from ibudget.services import categories

WARN_PERCENT = 90


class Level(StrEnum):
    ok = "ok"
    warning = "warning"  # at least WARN_PERCENT of the budget used
    over = "over"  # budget exceeded


def used_percent(spent_cents: int, limit_cents: int) -> int:
    """Share of the budget used, rounded down so it never shows 90% before the warning starts."""
    return spent_cents * 100 // limit_cents


def level_for(spent_cents: int, limit_cents: int) -> Level:
    if spent_cents > limit_cents:
        return Level.over
    if spent_cents * 100 >= limit_cents * WARN_PERCENT:
        return Level.warning
    return Level.ok


@dataclass(frozen=True)
class BudgetStatus:
    category: str
    limit_cents: int
    spent_cents: int

    @property
    def remaining_cents(self) -> int:
        return self.limit_cents - self.spent_cents

    @property
    def percent(self) -> int:
        return used_percent(self.spent_cents, self.limit_cents)

    @property
    def level(self) -> Level:
        return level_for(self.spent_cents, self.limit_cents)


def set_budget(repo: Repository, category: str, amount: str) -> Budget:
    found = categories.require(repo, category)
    cents = parse_positive_amount(amount)
    repo.set_budget(found.id, cents)
    return Budget(found.id, found.name, cents)


def remove(repo: Repository, category: str) -> None:
    found = categories.require(repo, category)
    if not repo.remove_budget(found.id):
        raise IBudgetError(f"Category '{found.name}' has no budget.")


def statuses(repo: Repository, month: Month) -> list[BudgetStatus]:
    """Every budget with what was spent in `month`, by category name."""
    spent = repo.totals_by_category(month.start, month.end)
    return [
        BudgetStatus(b.category, b.limit_cents, spent.get(b.category_id, 0))
        for b in repo.list_budgets()
    ]


def status_for(repo: Repository, category_id: int, month: Month) -> BudgetStatus | None:
    budget = repo.get_budget(category_id)
    if budget is None:
        return None
    spent = repo.total_between(month.start, month.end, category_id)
    return BudgetStatus(budget.category, budget.limit_cents, spent)
