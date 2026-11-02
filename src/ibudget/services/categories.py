import re
from dataclasses import dataclass

from ibudget.errors import IBudgetError
from ibudget.models import Category
from ibudget.repository import Repository

_NAME_PATTERN = re.compile(r"^\w[\w &-]{0,29}$")


@dataclass(frozen=True)
class CategoryOverview:
    name: str
    expense_count: int
    budget_cents: int | None


def normalize_name(name: str) -> str:
    """Category names are stored lowercase: 'Pet Care ' -> 'pet care'."""
    cleaned = " ".join(name.split()).lower()
    if not _NAME_PATTERN.match(cleaned):
        raise IBudgetError(
            f"'{name}' is not a valid category name: use 1-30 letters, digits, spaces, '-' or '&'."
        )
    return cleaned


def require(repo: Repository, name: str) -> Category:
    """The category called `name`, or a helpful error listing the known ones."""
    category = repo.find_category(name.strip())
    if category is None:
        known = ", ".join(c.name for c in repo.list_categories())
        raise IBudgetError(f"Unknown category '{name}'. Known categories: {known}.")
    return category


def overview(repo: Repository) -> list[CategoryOverview]:
    counts = repo.expense_counts()
    budgets = {b.category_id: b.limit_cents for b in repo.list_budgets()}
    return [
        CategoryOverview(c.name, counts.get(c.id, 0), budgets.get(c.id))
        for c in repo.list_categories()
    ]


def add(repo: Repository, name: str) -> Category:
    cleaned = normalize_name(name)
    if repo.find_category(cleaned):
        raise IBudgetError(f"Category '{cleaned}' already exists.")
    return repo.add_category(cleaned)


def rename(repo: Repository, old: str, new: str) -> Category:
    category = require(repo, old)
    cleaned = normalize_name(new)
    existing = repo.find_category(cleaned)
    if existing and existing.id != category.id:
        raise IBudgetError(f"Category '{cleaned}' already exists.")
    repo.rename_category(category.id, cleaned)
    return Category(category.id, cleaned)


@dataclass(frozen=True)
class Deletion:
    category: Category
    reassign_to: Category | None
    expense_count: int


def check_delete(repo: Repository, name: str, reassign_to: str | None = None) -> Deletion:
    """Validate a deletion without changing anything, so the CLI can confirm it first.

    A category that still has expenses can only be deleted when they are moved elsewhere.
    """
    category = require(repo, name)
    target = require(repo, reassign_to) if reassign_to else None
    if target and target.id == category.id:
        raise IBudgetError("Cannot reassign expenses to the category being deleted.")
    count = repo.count_expenses(category.id)
    if count and target is None:
        raise IBudgetError(
            f"Category '{category.name}' has {count} expense(s); "
            "use --reassign-to <category> to move them first."
        )
    return Deletion(category, target, count)


def delete(repo: Repository, name: str, reassign_to: str | None = None) -> Deletion:
    """Delete a category, moving its expenses to `reassign_to`. Its budget is deleted with it."""
    deletion = check_delete(repo, name, reassign_to)
    target_id = deletion.reassign_to.id if deletion.reassign_to else None
    repo.delete_category(deletion.category.id, target_id)
    return deletion
