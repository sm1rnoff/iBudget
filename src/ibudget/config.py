"""User settings stored in the database's `settings` table."""

import re
from collections.abc import Callable

from ibudget.db import DEFAULT_CURRENCY
from ibudget.errors import IBudgetError
from ibudget.repository import Repository


def _currency(value: str) -> str:
    code = value.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", code):
        raise IBudgetError(f"'{value}' is not a currency code; use three letters, e.g. EUR.")
    return code


# Each known key maps to a function that validates and normalizes its value.
SETTINGS: dict[str, Callable[[str], str]] = {"currency": _currency}
DEFAULTS = {"currency": DEFAULT_CURRENCY}


def _check_key(key: str) -> str:
    if key not in SETTINGS:
        raise IBudgetError(f"Unknown setting '{key}'. Known settings: {', '.join(SETTINGS)}.")
    return key


def get(repo: Repository, key: str) -> str:
    _check_key(key)
    return repo.get_setting(key, DEFAULTS[key])


def set(repo: Repository, key: str, value: str) -> str:
    normalized = SETTINGS[_check_key(key)](value)
    repo.set_setting(key, normalized)
    return normalized


def all_settings(repo: Repository) -> dict[str, str]:
    return {key: get(repo, key) for key in SETTINGS}


def currency(repo: Repository) -> str:
    return get(repo, "currency")
