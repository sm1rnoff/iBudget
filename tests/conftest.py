import datetime as dt

import pytest

from ibudget.repository import Repository


@pytest.fixture(autouse=True)
def db_path(tmp_path, monkeypatch):
    """A fresh database per test; IBUDGET_DB points at it so nothing touches real data."""
    path = tmp_path / "ibudget.db"
    monkeypatch.setenv("IBUDGET_DB", str(path))
    return path


@pytest.fixture
def repo(db_path):
    repository = Repository.open(db_path)
    yield repository
    repository.close()


@pytest.fixture
def add(repo):
    """Shortcut for inserting an expense by category name: add('2026-11-02', 1250, 'food')."""

    def _add(date: str, cents: int, category: str = "food", note: str = ""):
        found = repo.find_category(category)
        assert found is not None, category
        return repo.add_expense(dt.date.fromisoformat(date), cents, found.id, note)

    return _add
