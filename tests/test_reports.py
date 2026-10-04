"""Tests for the report math. Uses a throwaway in-memory database."""
import pytest

import db
import reports


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    yield c
    c.close()


def seed(conn):
    db.add_expense(conn, 40.0, "groceries", "weekly run", "2026-10-03")
    db.add_expense(conn, 60.0, "groceries", "costco", "2026-10-15")
    db.add_expense(conn, 25.0, "coffee", "", "2026-10-20")
    db.add_expense(conn, 100.0, "groceries", "old", "2026-09-01")  # different month


def test_category_totals_group_and_sum(conn):
    seed(conn)
    totals = dict(db.category_totals(conn, month="2026-10"))
    assert totals == {"groceries": 100.0, "coffee": 25.0}


def test_totals_respect_month_filter(conn):
    seed(conn)
    totals = dict(db.category_totals(conn, month="2026-09"))
    assert totals == {"groceries": 100.0}


def test_grand_total(conn):
    seed(conn)
    assert db.grand_total(conn, month="2026-10") == 125.0
    assert db.grand_total(conn, month="2026-11") == 0.0


def test_summary_text_lists_categories_and_grand_total(conn):
    seed(conn)
    text = reports.summary(conn, "2026-10")
    assert "groceries" in text and "coffee" in text
    assert "$125.00" in text


def test_summary_empty_month(conn):
    assert "No expenses recorded." in reports.summary(conn, "2026-11")


def test_budget_status_thresholds():
    assert reports.budget_status(50, 100) == "ok"
    assert reports.budget_status(80, 100) == "WARNING"
    assert reports.budget_status(99, 100) == "WARNING"
    assert reports.budget_status(100, 100) == "OVER"
    assert reports.budget_status(150, 100) == "OVER"


def test_budget_check_flags_warning_and_over(conn):
    db.add_expense(conn, 85.0, "coffee", "", "2026-10-05")
    db.add_expense(conn, 210.0, "groceries", "", "2026-10-06")
    db.set_budget(conn, "coffee", 100.0)
    db.set_budget(conn, "groceries", 200.0)
    db.set_budget(conn, "rent", 1500.0)  # no spending this month
    text = reports.budget_check(conn, "2026-10")
    assert "WARNING" in text   # coffee at 85%
    assert "OVER" in text       # groceries at 105%
    assert "rent" in text       # budgeted but unspent still listed


def test_budget_check_without_budgets(conn):
    assert "No budgets set." in reports.budget_check(conn, "2026-10")


def test_table_columns_line_up():
    lines = reports.format_table(["name", "spent"], [["groceries", "$42.18"], ["coffee", "$9.99"]])
    # separator matches the header width
    assert lines[1] == "-" * len(lines[0])
    # the value column starts at the same offset in the header and every row
    assert lines[0].index("spent") == lines[2].index("$") == lines[3].index("$")


def test_import_skips_bad_rows(conn, tmp_path):
    csv_file = tmp_path / "expenses.csv"
    csv_file.write_text(
        "id,amount,category,note,date\n"
        "1,12.5,groceries,ok,2026-10-01\n"
        "2,notanumber,coffee,bad amount,2026-10-02\n"
        "3,9.99,,missing category,2026-10-03\n"
    )
    imported, skipped = db.import_csv(conn, str(csv_file))
    assert (imported, skipped) == (1, 2)
    assert db.grand_total(conn) == 12.5
