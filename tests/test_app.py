"""Smoke tests for app.py — Flask test client against a throwaway database."""

import io
import os

import pytest

import db
from app import app

SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "..", "samples", "sample-expenses.csv")


@pytest.fixture
def client(tmp_path, monkeypatch):
    # point the app at a fresh database for each test
    monkeypatch.setenv("EXPENSE_DB", str(tmp_path / "test.db"))
    app.config["TESTING"] = True
    return app.test_client()


def _db_path(client):
    return os.environ["EXPENSE_DB"]


def seed(client, month="2026-10"):
    """Two expenses in the given month, straight into the test database."""
    conn = db.connect(_db_path(client))
    db.add_expense(conn, 42.18, "groceries", "weekly run", f"{month}-04")
    db.add_expense(conn, 6.50, "coffee", "latte", f"{month}-05")
    conn.close()


def test_dashboard_empty_db(client):
    resp = client.get("/?month=2026-10")
    assert resp.status_code == 200
    assert b"No expenses recorded yet" in resp.data
    assert b"expense-tracker" in resp.data


def test_add_expense_shows_on_dashboard(client):
    resp = client.post(
        "/add",
        data={"amount": "42.18", "category": "groceries",
              "note": "weekly run", "date": "2026-10-04", "month": "2026-10"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"$42.18" in resp.data
    assert b"groceries" in resp.data
    # redirected back to the month of the expense
    assert b"2026-10" in resp.data


def test_add_zero_amount_returns_error_not_500(client):
    resp = client.post(
        "/add",
        data={"amount": "0", "category": "groceries", "date": "2026-10-04",
              "month": "2026-10"},
    )
    assert resp.status_code == 400
    assert b"more than $0.00" in resp.data


@pytest.mark.parametrize("amount", ["nan", "inf", "-inf"])
def test_add_non_finite_amount_rejected(client, amount):
    # float() parses these, and nan <= 0 is False, so they used to be saved
    resp = client.post(
        "/add",
        data={"amount": amount, "category": "groceries", "date": "2026-10-04",
              "month": "2026-10"},
    )
    assert resp.status_code == 400
    assert b"more than $0.00" in resp.data
    conn = db.connect(_db_path(client))
    assert db.list_expenses(conn) == []
    conn.close()


@pytest.mark.parametrize("amount", ["nan", "inf", "-inf"])
def test_budget_non_finite_amount_rejected(client, amount):
    resp = client.post(
        "/budget",
        data={"category": "groceries", "amount": amount, "month": "2026-10"},
    )
    assert resp.status_code == 400
    assert b"more than $0.00" in resp.data
    conn = db.connect(_db_path(client))
    assert db.get_budgets(conn) == []
    conn.close()


def test_add_empty_category_returns_error_not_500(client):
    resp = client.post(
        "/add",
        data={"amount": "12.50", "category": "  ", "date": "2026-10-04",
              "month": "2026-10"},
    )
    assert resp.status_code == 400
    assert b"category" in resp.data.lower()


def test_budget_bar_shows_after_set(client):
    seed(client)
    resp = client.post(
        "/budget",
        data={"category": "groceries", "amount": "400", "month": "2026-10"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"groceries" in resp.data
    assert b"$400.00" in resp.data
    assert b"$42.18 of $400.00" in resp.data
    assert b"11% used" in resp.data  # 42.18 / 400


def test_chart_png_with_data_and_empty_month(client):
    seed(client)
    resp = client.get("/chart.png?month=2026-10")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"

    resp = client.get("/chart.png?month=2026-11")
    assert resp.status_code == 404
    assert b"Nothing to chart" in resp.data


def test_recurring_lists_seeded_charge(client):
    conn = db.connect(_db_path(client))
    for month in ("2026-08", "2026-09", "2026-10"):
        db.add_expense(conn, 1450.0, "rent", "", f"{month}-01")
    db.add_expense(conn, 42.0, "groceries", "one-off", "2026-10-03")
    conn.close()

    resp = client.get("/recurring")
    assert resp.status_code == 200
    assert b"rent" in resp.data
    assert b"$1,450.00" in resp.data
    assert b"3 months" in resp.data
    assert b"groceries" not in resp.data


def test_recurring_empty_state(client):
    resp = client.get("/recurring")
    assert resp.status_code == 200
    assert b"Nothing repeated" in resp.data


def test_import_export_round_trip(client, tmp_path, monkeypatch):
    seed(client)
    resp = client.get("/export")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert b"groceries" in resp.data
    assert b"coffee" in resp.data
    exported = resp.data

    # import the export into a fresh database — same rows, same count
    monkeypatch.setenv("EXPENSE_DB", str(tmp_path / "fresh.db"))
    resp = client.post(
        "/import",
        data={"csv": (io.BytesIO(exported), "expenses.csv"), "month": "2026-10"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert b"Imported 2 expense(s)." in resp.data

    conn = db.connect(str(tmp_path / "fresh.db"))
    assert db.grand_total(conn) == pytest.approx(48.68)
    assert len(db.list_expenses(conn)) == 2
    conn.close()


def test_import_counts_bad_rows(client):
    resp = client.post(
        "/import",
        data={
            "csv": (
                io.BytesIO(
                    b"id,amount,category,note,date\n"
                    b"1,12.5,groceries,ok,2026-10-01\n"
                    b"2,notanumber,coffee,bad amount,2026-10-02\n"
                ),
                "expenses.csv",
            ),
            "month": "2026-10",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert b"Imported 1 expense(s). Skipped 1 bad row(s)." in resp.data


def test_sample_csv_downloads(client):
    resp = client.get("/sample")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert b"1450.00,rent" in resp.data
    assert resp.data.count(b"\n") == 13  # header + 12 rows


def test_month_navigation_links(client):
    resp = client.get("/?month=2026-10")
    assert resp.status_code == 200
    assert b"2026-09" in resp.data
    assert b"2026-11" in resp.data
