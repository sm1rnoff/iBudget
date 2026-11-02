import datetime as dt
from dataclasses import dataclass

from ibudget.errors import IBudgetError


@dataclass(frozen=True, order=True)
class Month:
    year: int
    month: int

    @classmethod
    def parse(cls, text: str) -> Month:
        try:
            parsed = dt.datetime.strptime(text.strip(), "%Y-%m")
        except ValueError:
            raise IBudgetError(f"'{text}' is not a month; use YYYY-MM, e.g. 2026-11.") from None
        return cls(parsed.year, parsed.month)

    @classmethod
    def of(cls, day: dt.date) -> Month:
        return cls(day.year, day.month)

    @classmethod
    def current(cls) -> Month:
        return cls.of(dt.date.today())

    def shift(self, months: int) -> Month:
        index = self.year * 12 + (self.month - 1) + months
        return Month(index // 12, index % 12 + 1)

    def previous(self) -> Month:
        return self.shift(-1)

    def next(self) -> Month:
        return self.shift(1)

    @property
    def start(self) -> dt.date:
        """First day of the month (inclusive)."""
        return dt.date(self.year, self.month, 1)

    @property
    def end(self) -> dt.date:
        """First day of the next month (exclusive)."""
        return self.next().start

    @property
    def label(self) -> str:
        return self.start.strftime("%B %Y")

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


def parse_date(text: str, fmt: str = "%Y-%m-%d") -> dt.date:
    try:
        return dt.datetime.strptime(text.strip(), fmt).date()
    except ValueError:
        raise IBudgetError(f"'{text}' is not a valid date (expected format {fmt}).") from None
