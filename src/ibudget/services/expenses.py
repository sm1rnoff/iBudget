import datetime as dt

from ibudget.errors import IBudgetError
from ibudget.models import Expense
from ibudget.money import parse_positive_amount
from ibudget.period import Month
from ibudget.repository import ExpenseSort, Repository
from ibudget.services import categories


def add(
    repo: Repository,
    amount: str,
    category: str,
    note: str = "",
    date: dt.date | None = None,
) -> Expense:
    cents = parse_positive_amount(amount)
    found = categories.require(repo, category)
    return repo.add_expense(date or dt.date.today(), cents, found.id, note.strip())


def get(repo: Repository, expense_id: int) -> Expense:
    expense = repo.get_expense(expense_id)
    if expense is None:
        raise IBudgetError(f"There is no expense #{expense_id}.")
    return expense


def find(
    repo: Repository,
    *,
    month: Month | None = None,
    category: str | None = None,
    min_amount: str | None = None,
    max_amount: str | None = None,
    sort: ExpenseSort = "date",
    limit: int | None = None,
) -> list[Expense]:
    return repo.list_expenses(
        start=month.start if month else None,
        end=month.end if month else None,
        category_id=categories.require(repo, category).id if category else None,
        min_cents=parse_positive_amount(min_amount) if min_amount else None,
        max_cents=parse_positive_amount(max_amount) if max_amount else None,
        sort=sort,
        limit=limit,
    )


def edit(
    repo: Repository,
    expense_id: int,
    *,
    amount: str | None = None,
    category: str | None = None,
    date: dt.date | None = None,
    note: str | None = None,
) -> Expense:
    get(repo, expense_id)
    if amount is None and category is None and date is None and note is None:
        raise IBudgetError("Nothing to change: pass --amount, --category, --date or --note.")
    repo.update_expense(
        expense_id,
        amount_cents=parse_positive_amount(amount) if amount is not None else None,
        category_id=categories.require(repo, category).id if category is not None else None,
        date=date,
        note=note.strip() if note is not None else None,
    )
    return get(repo, expense_id)


def delete(repo: Repository, expense_id: int) -> Expense:
    expense = get(repo, expense_id)
    repo.delete_expense(expense_id)
    return expense
