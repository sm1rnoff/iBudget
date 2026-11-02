from ibudget.period import Month
from ibudget.services import budgets, reports
from ibudget.services.budgets import Level


def test_percent_helpers():
    assert reports.percent(1, 3) == 33
    assert reports.percent(5, 0) is None
    assert reports.change_percent(108, 100) == 8
    assert reports.change_percent(50, 0) is None


def test_monthly_report(repo, add):
    # October
    add("2026-10-03", 65000, "housing")
    add("2026-10-10", 20000, "food")
    add("2026-10-12", 3000, "health")
    # November (month boundaries: the 1st and the 30th count, December 1st does not)
    add("2026-11-01", 65000, "housing")
    add("2026-11-15", 21000, "food")
    add("2026-11-30", 6000, "food")
    add("2026-12-01", 99900, "food")
    budgets.set_budget(repo, "food", "250")
    budgets.set_budget(repo, "shopping", "100")

    report = reports.monthly_report(repo, Month(2026, 11))

    assert report.total_cents == 92000
    assert report.previous_total_cents == 88000
    assert report.change_percent == 5
    rows = {row.category: row for row in report.rows}
    # Categories with spending in either month or with a budget; largest spending first.
    assert [row.category for row in report.rows] == ["housing", "food", "health", "shopping"]
    food = rows["food"]
    assert (food.spent_cents, food.previous_cents, food.share_percent) == (27000, 20000, 29)
    assert (food.change_percent, food.budget_percent, food.budget_level) == (35, 108, Level.over)
    assert (rows["health"].spent_cents, rows["health"].change_percent) == (0, -100)
    assert rows["housing"].change_percent == 0
    assert rows["housing"].budget_level is None
    assert (rows["shopping"].budget_percent, rows["shopping"].change_percent) == (0, None)


def test_empty_month(repo):
    report = reports.monthly_report(repo, Month(2020, 1))
    assert (report.rows, report.total_cents, report.change_percent) == ([], 0, None)


def test_trend_crosses_year_boundary(repo, add):
    add("2026-01-15", 1000, "food")
    add("2025-12-31", 500, "food")
    add("2025-08-01", 700, "food")  # outside the 6-month window
    points = reports.trend(repo, Month(2026, 1))
    assert [str(p.month) for p in points] == [
        "2025-08", "2025-09", "2025-10", "2025-11", "2025-12", "2026-01",
    ]  # fmt: skip
    assert [p.total_cents for p in points] == [700, 0, 0, 0, 500, 1000]
    assert len(reports.trend(repo, Month(2026, 1), months=3)) == 3
