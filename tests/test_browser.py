"""The HTMX wiring, checked in a real browser (Chromium through pytest-playwright).

test_web.py covers what each route returns. These tests cover what only a browser shows:
clicks and filter changes swap the right fragment in place, without a full page reload, and
the address bar, tab title and back button follow. HTMX is loaded from its CDN, so they need
network access; skip them with `pytest -m "not browser"`.
"""

import datetime as dt
import re
import threading
import time

import pytest
import uvicorn
from playwright.sync_api import Page, expect

from ibudget.repository import Repository
from ibudget.web.app import create_app

pytestmark = pytest.mark.browser

EXPENSES = [
    ("2026-10-10", 20000, "food", "October groceries"),
    ("2026-11-01", 65000, "housing", "Rent"),
    ("2026-11-02", 1250, "food", "Lunch"),
    ("2026-11-20", 26000, "food", "Groceries"),
    ("2026-11-25", 3000, "food", "Dinner"),
]


@pytest.fixture(scope="session")
def server_url(tmp_path_factory):
    """The dashboard on a seeded temporary database, served by uvicorn in a background thread."""
    db_path = tmp_path_factory.mktemp("browser") / "ibudget.db"
    repo = Repository.open(db_path)
    for date, cents, category, note in EXPENSES:
        repo.add_expense(dt.date.fromisoformat(date), cents, repo.find_category(category).id, note)
    repo.close()

    server = uvicorn.Server(
        uvicorn.Config(create_app(db_path), host="127.0.0.1", port=0, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert thread.is_alive() and time.monotonic() < deadline, "dashboard server did not start"
        time.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]  # port=0 lets the OS pick a free one
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture
def dashboard(page: Page, server_url) -> Page:
    """November 2026, with a marker on `window` that a full page reload would wipe out."""
    page.goto(f"{server_url}/?month=2026-11")
    page.wait_for_function("typeof htmx !== 'undefined'")
    page.evaluate("window.notReloaded = true")
    return page


def assert_not_reloaded(page: Page) -> None:
    assert page.evaluate("window.notReloaded === true"), "the page was fully reloaded"


def wait_until_settled(page: Page) -> None:
    """Call after checking swapped-in content, before using it: HTMX only wires up new
    elements (like the re-rendered filter form) when it settles, ~20 ms after the swap."""
    expect(page.locator(".htmx-request, .htmx-settling")).to_have_count(0)


def test_month_link_swaps_month_in_place(dashboard):
    dashboard.get_by_role("navigation", name="Month").get_by_role(
        "link", name="October 2026"
    ).click()

    expect(dashboard.get_by_role("heading", level=1)).to_have_text("October 2026")
    expect(dashboard.locator("#expenses td.note")).to_have_text(["October groceries"])
    expect(dashboard).to_have_url(re.compile(r"/\?month=2026-10$"))
    expect(dashboard).to_have_title("iBudget · October 2026")
    assert_not_reloaded(dashboard)


def test_back_button_restores_previous_month(dashboard):
    dashboard.get_by_role("navigation", name="Month").get_by_role(
        "link", name="October 2026"
    ).click()
    expect(dashboard).to_have_url(re.compile(r"/\?month=2026-10$"))
    wait_until_settled(dashboard)

    dashboard.go_back()

    expect(dashboard.get_by_role("heading", level=1)).to_have_text("November 2026")
    expect(dashboard).to_have_url(re.compile(r"/\?month=2026-11$"))
    expect(dashboard).to_have_title("iBudget · November 2026")
    assert_not_reloaded(dashboard)


def test_trend_bar_opens_its_month(dashboard):
    dashboard.get_by_title("October 2026:").click()

    expect(dashboard.get_by_role("heading", level=1)).to_have_text("October 2026")
    expect(dashboard).to_have_url(re.compile(r"/\?month=2026-10$"))
    assert_not_reloaded(dashboard)


def test_filter_and_sort_swap_only_the_expense_table(dashboard):
    notes = dashboard.locator("#expenses td.note")
    expect(notes).to_have_text(["Dinner", "Groceries", "Lunch", "Rent"])  # newest first

    dashboard.get_by_label("Category").select_option("food")
    expect(notes).to_have_text(["Dinner", "Groceries", "Lunch"])
    expect(dashboard).to_have_url(re.compile(r"/\?month=2026-11&category=food$"))
    wait_until_settled(dashboard)

    dashboard.get_by_label("Sort").select_option(label="Largest first")
    expect(notes).to_have_text(["Groceries", "Dinner", "Lunch"])
    expect(dashboard).to_have_url(re.compile(r"/\?month=2026-11&category=food&sort=amount$"))

    # The re-rendered form keeps both choices, and the month itself did not change.
    expect(dashboard.get_by_label("Category")).to_have_value("food")
    expect(dashboard.get_by_label("Sort")).to_have_value("amount")
    expect(dashboard.get_by_role("heading", level=1)).to_have_text("November 2026")
    assert_not_reloaded(dashboard)
