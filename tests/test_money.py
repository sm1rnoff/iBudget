import datetime as dt

import pytest

from ibudget.errors import IBudgetError
from ibudget.money import format_amount, parse_amount, parse_positive_amount, plain_amount
from ibudget.period import Month, parse_date


@pytest.mark.parametrize(
    ("text", "cents"),
    [
        ("12", 1200),
        ("12.5", 1250),
        ("12,50", 1250),
        (" 0.01 ", 1),
        ("1,234.56", 123456),
        ("1.234,56", 123456),
        ("1 234,56", 123456),
        ("-45.10", -4510),
        ("0.005", 1),  # rounds half up to whole cents
    ],
)
def test_parse_amount(text, cents):
    assert parse_amount(text) == cents


@pytest.mark.parametrize("text", ["", "abc", "1.2.3", "NaN", "Infinity"])
def test_parse_amount_rejects_garbage(text):
    with pytest.raises(IBudgetError):
        parse_amount(text)


@pytest.mark.parametrize("text", ["0", "-5"])
def test_parse_positive_amount_rejects_zero_and_negative(text):
    with pytest.raises(IBudgetError, match="greater than zero"):
        parse_positive_amount(text)


def test_format_amount():
    assert format_amount(124750) == "1,247.50"
    assert format_amount(5, "EUR") == "0.05 EUR"
    assert format_amount(-4510) == "-45.10"
    assert plain_amount(124750) == "1247.50"


def test_month_parse_and_navigation():
    month = Month.parse("2026-12")
    assert str(month) == "2026-12"
    assert month.start == dt.date(2026, 12, 1)
    assert month.end == dt.date(2027, 1, 1)
    assert month.next() == Month(2027, 1)
    assert Month(2026, 1).previous() == Month(2025, 12)
    assert month.shift(-14) == Month(2025, 10)
    assert month.label == "December 2026"


@pytest.mark.parametrize("text", ["2026-13", "2026", "nov", ""])
def test_month_parse_rejects_invalid(text):
    with pytest.raises(IBudgetError, match="YYYY-MM"):
        Month.parse(text)


def test_parse_date():
    assert parse_date("2026-11-02") == dt.date(2026, 11, 2)
    assert parse_date("02.11.2026", "%d.%m.%Y") == dt.date(2026, 11, 2)
    with pytest.raises(IBudgetError):
        parse_date("2026-02-30")
