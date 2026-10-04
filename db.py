"""SQLite storage for the expense tracker.

Two tables, nothing fancy:
  expenses: id, amount, category, note, date
  budgets:   category, amount
"""
import csv
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS expenses (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    amount   REAL NOT NULL,
    category TEXT NOT NULL,
    note     TEXT NOT NULL DEFAULT '',
    date     TEXT NOT NULL          -- stored as YYYY-MM-DD
);
CREATE TABLE IF NOT EXISTS budgets (
    category TEXT PRIMARY KEY,
    amount   REAL NOT NULL
);
"""


def connect(path):
    """Open (and create if needed) the tracker database."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def add_expense(conn, amount, category, note="", date=None):
    """Insert an expense, return its new id."""
    cur = conn.execute(
        "INSERT INTO expenses (amount, category, note, date) VALUES (?, ?, ?, ?)",
        (amount, category.strip(), note, date),
    )
    conn.commit()
    return cur.lastrowid


def list_expenses(conn, month=None, category=None):
    """Return matching expenses, newest first."""
    query = "SELECT id, amount, category, note, date FROM expenses"
    where, params = [], []
    if month:
        where.append("substr(date, 1, 7) = ?")
        params.append(month)
    if category:
        where.append("category = ?")
        params.append(category)
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY date DESC, id DESC"
    return conn.execute(query, params).fetchall()


def category_totals(conn, month=None):
    """(category, total) pairs for the given month (or all time), biggest first."""
    query = "SELECT category, SUM(amount) AS total FROM expenses"
    params = []
    if month:
        query += " WHERE substr(date, 1, 7) = ?"
        params.append(month)
    query += " GROUP BY category ORDER BY total DESC"
    return [(row["category"], row["total"]) for row in conn.execute(query, params)]


def grand_total(conn, month=None):
    query = "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses"
    params = []
    if month:
        query += " WHERE substr(date, 1, 7) = ?"
        params.append(month)
    return conn.execute(query, params).fetchone()["total"]


def set_budget(conn, category, amount):
    """Create or overwrite the monthly budget for a category."""
    conn.execute(
        "INSERT INTO budgets (category, amount) VALUES (?, ?) "
        "ON CONFLICT(category) DO UPDATE SET amount = excluded.amount",
        (category.strip(), amount),
    )
    conn.commit()


def get_budgets(conn):
    """[(category, amount)] sorted by category."""
    rows = conn.execute("SELECT category, amount FROM budgets ORDER BY category").fetchall()
    return [(r["category"], r["amount"]) for r in rows]


def export_csv(conn, path):
    """Dump all expenses to a CSV file. Returns the number of rows written."""
    rows = conn.execute(
        "SELECT id, amount, category, note, date FROM expenses ORDER BY date, id"
    ).fetchall()
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "amount", "category", "note", "date"])
        writer.writerows([tuple(r) for r in rows])
    return len(rows)


def import_csv(conn, path):
    """Load expenses from a CSV file. Returns (imported, skipped).

    Bad rows are counted and skipped rather than aborting the whole file --
    the one time I did it the strict way I lost 40 rows to a single typo.
    """
    imported, skipped = 0, 0
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                amount = float(row["amount"])
                category = (row.get("category") or "").strip()
                note = row.get("note") or ""
                date = (row.get("date") or "").strip()
                if not category or not date:
                    raise ValueError("missing category/date")
                add_expense(conn, amount, category, note, date)
                imported += 1
            except (ValueError, KeyError, TypeError):
                skipped += 1
    return imported, skipped


def default_db_path():
    return os.environ.get("EXPENSE_DB", "expenses.db")
