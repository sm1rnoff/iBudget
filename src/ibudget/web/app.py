"""Read-only HTMX dashboard. Routes call the same services as the CLI; no SQL here."""

from collections.abc import Iterator
from html import escape
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ibudget import __version__, config
from ibudget.errors import IBudgetError
from ibudget.money import format_amount
from ibudget.period import Month
from ibudget.repository import Repository
from ibudget.services import budgets, categories, expenses, reports

WEB_DIR = Path(__file__).parent
HTMX_URL = "https://cdn.jsdelivr.net/npm/htmx.org@2.0.4/dist/htmx.min.js"
TREND_MONTHS = 6

Sort = Literal["date", "amount"]


def page_url(month: Month, category: str | None = None, sort: Sort = "date") -> str:
    """Canonical full-page URL for a dashboard state (default values left out)."""
    params = {"month": str(month)}
    if category:
        params["category"] = category
    if sort != "date":
        params["sort"] = sort
    return f"/?{urlencode(params)}"


def _month(month: str | None = None) -> Month:
    return Month.parse(month) if month else Month.current()


MonthParam = Annotated[Month, Depends(_month)]


def _expenses_context(
    repo: Repository, month: Month, category: str | None, sort: Sort
) -> dict[str, object]:
    found = expenses.find(repo, month=month, category=category or None, sort=sort)
    return {
        "expenses": found,
        "expenses_total": sum(e.amount_cents for e in found),
        "category": category or "",
        "sort": sort,
        "category_names": [c.name for c in categories.overview(repo)],
    }


def _month_context(repo: Repository, month: Month) -> dict[str, object]:
    report = reports.monthly_report(repo, month)
    statuses = budgets.statuses(repo, month)
    trend = reports.trend(repo, month, TREND_MONTHS)
    return {
        "report": report,
        "spending_rows": [row for row in report.rows if row.spent_cents],
        "budgets": statuses,
        "budgets_over": sum(1 for s in statuses if s.level is budgets.Level.over),
        "budgets_warning": sum(1 for s in statuses if s.level is budgets.Level.warning),
        "trend": trend,
        "trend_max": max(p.total_cents for p in trend) or 1,
    }


def create_app(db_path: Path | str | None = None) -> FastAPI:
    app = FastAPI(title="iBudget", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=WEB_DIR / "templates")
    templates.env.filters["money"] = format_amount
    templates.env.globals.update(page_url=page_url, htmx_url=HTMX_URL, version=__version__)

    def get_repo() -> Iterator[Repository]:
        repo = Repository.open(db_path)
        try:
            yield repo
        finally:
            repo.close()

    RepoDep = Annotated[Repository, Depends(get_repo)]

    @app.exception_handler(IBudgetError)
    def user_error(request: Request, error: IBudgetError) -> HTMLResponse:
        return HTMLResponse(f'<p class="error">{escape(str(error))}</p>', status_code=400)

    def render(request: Request, template: str, context: dict, push_url: str | None = None):
        response = templates.TemplateResponse(request, template, context)
        if push_url:
            # Lets HTMX keep the address bar on the shareable full-page URL after a swap.
            response.headers["HX-Push-Url"] = push_url
        return response

    @app.get("/", response_class=HTMLResponse)
    def dashboard(
        request: Request,
        month: MonthParam,
        repo: RepoDep,
        category: str | None = None,
        sort: Sort = "date",
    ):
        context = {
            "month": month,
            "currency": config.currency(repo),
            **_month_context(repo, month),
            **_expenses_context(repo, month, category, sort),
        }
        return render(request, "dashboard.html", context)

    @app.get("/partials/month", response_class=HTMLResponse)
    def month_partial(
        request: Request,
        month: MonthParam,
        repo: RepoDep,
    ):
        """Everything that depends on the month: cards, bars, trend and the expense table."""
        context = {
            "partial": True,  # adds a <title> so HTMX updates the browser tab title
            "month": month,
            "currency": config.currency(repo),
            **_month_context(repo, month),
            **_expenses_context(repo, month, None, "date"),
        }
        return render(request, "partials/month.html", context, page_url(month))

    @app.get("/partials/expenses", response_class=HTMLResponse)
    def expenses_partial(
        request: Request,
        month: MonthParam,
        repo: RepoDep,
        category: str | None = None,
        sort: Sort = "date",
    ):
        """Only the expense table, for the category filter and sorting."""
        context = {
            "month": month,
            "currency": config.currency(repo),
            **_expenses_context(repo, month, category, sort),
        }
        return render(
            request, "partials/expenses.html", context, page_url(month, category or None, sort)
        )

    return app
