from dataclasses import dataclass

from ibudget.period import Month
from ibudget.repository import Repository
from ibudget.services.budgets import Level, level_for, used_percent


def percent(part: int, whole: int) -> int | None:
    """`part` as a whole-number percentage of `whole`; None when `whole` is zero."""
    return round(part * 100 / whole) if whole else None


def change_percent(current: int, previous: int) -> int | None:
    """Change from `previous` to `current` in percent; None when there is nothing to compare."""
    return percent(current - previous, previous)


@dataclass(frozen=True)
class ReportRow:
    category: str
    spent_cents: int
    previous_cents: int
    budget_cents: int | None
    share_percent: int  # of the month's total

    @property
    def change_percent(self) -> int | None:
        return change_percent(self.spent_cents, self.previous_cents)

    @property
    def budget_percent(self) -> int | None:
        return used_percent(self.spent_cents, self.budget_cents) if self.budget_cents else None

    @property
    def budget_level(self) -> Level | None:
        return level_for(self.spent_cents, self.budget_cents) if self.budget_cents else None


@dataclass(frozen=True)
class MonthlyReport:
    month: Month
    rows: list[ReportRow]
    total_cents: int
    previous_total_cents: int

    @property
    def change_percent(self) -> int | None:
        return change_percent(self.total_cents, self.previous_total_cents)


@dataclass(frozen=True)
class TrendPoint:
    month: Month
    total_cents: int


def monthly_report(repo: Repository, month: Month) -> MonthlyReport:
    """Spending per category in `month`, compared with the previous month and the budgets.

    A category appears when it has spending in either month or a budget. Largest spending first.
    """
    previous = month.previous()
    current_totals = repo.totals_by_category(month.start, month.end)
    previous_totals = repo.totals_by_category(previous.start, previous.end)
    budgets = {b.category_id: b.limit_cents for b in repo.list_budgets()}
    total = sum(current_totals.values())

    rows = [
        ReportRow(
            category=category.name,
            spent_cents=current_totals.get(category.id, 0),
            previous_cents=previous_totals.get(category.id, 0),
            budget_cents=budgets.get(category.id),
            share_percent=percent(current_totals.get(category.id, 0), total) or 0,
        )
        for category in repo.list_categories()
        if category.id in current_totals or category.id in previous_totals or category.id in budgets
    ]
    rows.sort(key=lambda row: (-row.spent_cents, row.category))
    return MonthlyReport(month, rows, total, sum(previous_totals.values()))


def trend(repo: Repository, month: Month, months: int = 6) -> list[TrendPoint]:
    """Monthly totals for the `months` months ending with `month`, oldest first."""
    points = []
    for offset in range(months - 1, -1, -1):
        current = month.shift(-offset)
        points.append(TrendPoint(current, repo.total_between(current.start, current.end)))
    return points
