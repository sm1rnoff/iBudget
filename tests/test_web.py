import pytest
from fastapi.testclient import TestClient

from ibudget.period import Month
from ibudget.services import budgets
from ibudget.web.app import HTMX_URL, create_app, page_url


@pytest.fixture
def client(db_path):
    with TestClient(create_app(db_path)) as test_client:
        yield test_client


@pytest.fixture
def november(repo, add):
    add("2026-10-10", 20000, "food", "October groceries")
    add("2026-11-01", 65000, "housing", "Rent")
    add("2026-11-02", 1250, "food", "Lunch")
    add("2026-11-20", 26000, "food", "Groceries")
    budgets.set_budget(repo, "food", "250")
    budgets.set_budget(repo, "transport", "100")


def test_page_url():
    assert page_url(Month(2026, 11)) == "/?month=2026-11"
    assert page_url(Month(2026, 11), "pet care", "amount") == (
        "/?month=2026-11&category=pet+care&sort=amount"
    )


def test_full_page(client, november):
    response = client.get("/?month=2026-11")
    assert response.status_code == 200
    html = response.text
    assert html.startswith("<!doctype html>")
    assert HTMX_URL in html
    assert "<h1>November 2026</h1>" in html
    assert html.count("<title>") == 1
    assert "922.50" in html  # total spent
    assert "+361%" in html  # vs October (200.00 -> 922.50)
    assert "1 <small>over</small> · 0 <small>near</small>" in html
    assert 'class="bar-fill level-over" style="width: 100%"' in html  # food 109%, capped bar
    assert 'class="bar-fill level-ok" style="width: 0%"' in html  # transport
    assert "Groceries" in html and "October groceries" not in html
    assert html.count('class="trend-item') == 6


def test_default_month_is_current(client):
    assert f"<h1>{Month.current().label}</h1>" in client.get("/").text


def test_month_partial_is_a_fragment_and_sets_url(client, november):
    response = client.get("/partials/month?month=2026-10", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert "<html" not in response.text
    assert "<h1>October 2026</h1>" in response.text
    assert "<title>iBudget · October 2026</title>" in response.text
    assert "October groceries" in response.text
    assert response.headers["HX-Push-Url"] == "/?month=2026-10"


def test_expenses_partial_filters_and_sorts(client, november):
    response = client.get("/partials/expenses?month=2026-11&category=food&sort=amount")
    html = response.text
    assert response.status_code == 200
    assert "Rent" not in html
    assert html.index("Groceries") < html.index("Lunch")  # largest first
    assert "2 expense(s)" in html
    assert '<option value="food" selected>' in html
    assert response.headers["HX-Push-Url"] == "/?month=2026-11&category=food&sort=amount"


def test_full_page_keeps_filters(client, november):
    html = client.get("/?month=2026-11&category=housing").text
    assert "Rent" in html and "Lunch" not in html


def test_empty_month(client):
    html = client.get("/?month=2020-01").text
    assert "No spending this month." in html
    assert "No budgets yet" in html
    assert "No expenses for January 2020." in html


@pytest.mark.parametrize(
    ("url", "status", "message"),
    [
        ("/?month=2026-13", 400, "YYYY-MM"),
        ("/partials/month?month=nope", 400, "YYYY-MM"),
        ("/partials/expenses?month=2026-11&category=pets", 400, "Unknown category"),
        ("/partials/expenses?month=2026-11&sort=price", 422, ""),
    ],
)
def test_bad_requests(client, url, status, message):
    response = client.get(url)
    assert response.status_code == status
    assert message in response.text


def test_read_only_and_static(client):
    assert client.post("/").status_code == 405
    assert client.get("/docs").status_code == 404
    css = client.get("/static/dashboard.css")
    assert css.status_code == 200
    assert "prefers-color-scheme" in css.text


def test_html_is_escaped(client, repo, add):
    add("2026-11-02", 100, "food", "<script>alert(1)</script>")
    html = client.get("/?month=2026-11").text
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
