"""Money helpers. Amounts are always integer cents inside the app."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from ibudget.errors import IBudgetError


def parse_amount(text: str) -> int:
    """Parse '12.5', '12,50', '1,234.56', '1.234,56' or '-3' into signed integer cents."""
    cleaned = text.strip().replace(" ", "").replace(" ", "")
    if "," in cleaned and "." in cleaned:
        # Whichever separator comes last is the decimal one; the other groups thousands.
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise IBudgetError(f"'{text}' is not a valid amount.") from None
    if not value.is_finite():
        raise IBudgetError(f"'{text}' is not a valid amount.")
    return int((value * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def parse_positive_amount(text: str) -> int:
    cents = parse_amount(text)
    if cents <= 0:
        raise IBudgetError(f"Amount must be greater than zero, got '{text}'.")
    return cents


def format_amount(cents: int, currency: str | None = None) -> str:
    """Human-readable amount with thousands separators, e.g. '1,247.50 EUR'."""
    text = f"{Decimal(cents) / 100:,.2f}"
    return f"{text} {currency}" if currency else text


def plain_amount(cents: int) -> str:
    """Machine-friendly amount without grouping, e.g. '1247.50' (used for CSV)."""
    return f"{Decimal(cents) / 100:.2f}"
