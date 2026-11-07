"""expense-tracker web UI: a dashboard for the month's spending.

Thin layer over db.py / reports.py / charts.py — the CLI in tracker.py is
untouched and still the same code underneath. Each request opens its own
sqlite connection (db.default_db_path() respects $EXPENSE_DB) and closes
it afterwards, so tests can point the app at a throwaway database.
"""

import datetime
import io
import os
import re
import tempfile

from flask import Flask, abort, g, redirect, render_template, request, send_file, url_for

import charts
import db
import reports

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB uploads

MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RECENT_ROWS = 15


def get_conn():
    """One sqlite connection per request, closed in teardown."""
    if "conn" not in g:
        g.conn = db.connect(db.default_db_path())
    return g.conn


@app.teardown_appcontext
def close_conn(_exc):
    conn = g.pop("conn", None)
    if conn is not None:
        conn.close()


def money(amount):
    return f"${amount:,.2f}"


def current_month():
    return datetime.date.today().strftime("%Y-%m")


def parse_month(value):
    """A YYYY-MM string, or the current month when it is missing/invalid."""
    if value and MONTH_RE.match(value):
        try:
            datetime.datetime.strptime(value, "%Y-%m")
            return value
        except ValueError:
            pass
    return current_month()


def shift_month(month, delta):
    year, mon = int(month[:4]), int(month[5:7])
    mon += delta
    while mon < 1:
        mon += 12
        year -= 1
    while mon > 12:
        mon -= 12
        year += 1
    return f"{year:04d}-{mon:02d}"


def dashboard_data(month):
    """Everything the dashboard template needs for one month."""
    conn = get_conn()
    totals = db.category_totals(conn, month)
    total = db.grand_total(conn, month)
    count = len(db.list_expenses(conn, month=month))
    top_category, top_total = totals[0] if totals else (None, 0.0)

    # budget bars: spent vs limit for every budget, with its ok/WARNING/OVER state
    spent_by_cat = dict(totals)
    budget_rows = []
    over_or_warning = 0
    for category, limit in db.get_budgets(conn):
        spent = spent_by_cat.get(category, 0.0)
        pct = (spent / limit * 100) if limit else 0.0
        status = reports.budget_status(spent, limit)
        if status in ("WARNING", "OVER"):
            over_or_warning += 1
        budget_rows.append({
            "category": category,
            "spent": spent,
            "limit": limit,
            "pct": pct,
            "status": status,
        })

    return {
        "month": month,
        "prev_month": shift_month(month, -1),
        "next_month": shift_month(month, 1),
        "today": datetime.date.today().isoformat(),
        "total": total,
        "count": count,
        "top_category": top_category,
        "top_total": top_total,
        "over_or_warning": over_or_warning,
        "categories": [
            {"name": cat, "total": amt, "share": amt / total * 100 if total else 0.0}
            for cat, amt in totals
        ],
        "budgets": budget_rows,
        "recent": db.list_expenses(conn, month=month)[:RECENT_ROWS],
        "has_chart": bool(totals),
    }


def render_dashboard(month, error=None, message=None, status=200):
    data = dashboard_data(month)
    data["error"] = error
    data["message"] = message
    return render_template("index.html", **data), status


@app.route("/", methods=["GET"])
def index():
    return render_dashboard(parse_month(request.args.get("month")))


@app.route("/add", methods=["POST"])
def add_expense():
    month = parse_month(request.form.get("month"))
    amount_raw = (request.form.get("amount") or "").strip()
    category = (request.form.get("category") or "").strip()
    note = (request.form.get("note") or "").strip()
    date = (request.form.get("date") or "").strip() or datetime.date.today().isoformat()

    try:
        amount = float(amount_raw)
    except ValueError:
        return render_dashboard(
            month, error="Enter an amount as a number, like 12.50.", status=400
        )
    if amount <= 0:
        return render_dashboard(
            month, error="Amount must be more than $0.00.", status=400
        )
    if not category:
        return render_dashboard(
            month, error="Enter a category, like groceries or rent.", status=400
        )
    if not DATE_RE.match(date):
        return render_dashboard(
            month, error="Date must look like 2026-10-04.", status=400
        )
    try:
        datetime.datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return render_dashboard(
            month, error=f"{date} is not a real date.", status=400
        )

    db.add_expense(get_conn(), amount, category, note, date)
    return redirect(url_for("index", month=date[:7]))


@app.route("/budget", methods=["POST"])
def set_budget():
    month = parse_month(request.form.get("month"))
    category = (request.form.get("category") or "").strip()
    amount_raw = (request.form.get("amount") or "").strip()

    try:
        amount = float(amount_raw)
    except ValueError:
        return render_dashboard(
            month, error="Enter a budget amount as a number, like 400.", status=400
        )
    if not category:
        return render_dashboard(
            month, error="Enter a category to set a budget for.", status=400
        )
    if amount <= 0:
        return render_dashboard(
            month, error="Budget must be more than $0.00.", status=400
        )

    db.set_budget(get_conn(), category, amount)
    return redirect(url_for("index", month=month))


@app.route("/recurring", methods=["GET"])
def recurring_page():
    hits = db.recurring(get_conn())
    return render_template(
        "recurring.html",
        hits=[{"category": cat, "amount": amt, "months": n} for cat, amt, n in hits],
    )


@app.route("/import", methods=["POST"])
def import_csv():
    month = parse_month(request.form.get("month"))
    upload = request.files.get("csv")
    if upload is None or not upload.filename:
        return render_dashboard(month, error="Pick a CSV file to import.", status=400)
    if not upload.filename.lower().endswith(".csv"):
        return render_dashboard(
            month, error="That file is not a CSV — pick a .csv file.", status=400
        )

    # db.import_csv reads from a path, so stage the upload in a temp file
    fd, path = tempfile.mkstemp(suffix=".csv")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(upload.read())
        imported, skipped = db.import_csv(get_conn(), path)
    finally:
        os.unlink(path)

    message = f"Imported {imported} expense(s)."
    if skipped:
        message += f" Skipped {skipped} bad row(s)."
    return render_dashboard(month, message=message)


@app.route("/export", methods=["GET"])
def export_csv():
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        db.export_csv(get_conn(), path)
        with open(path, "rb") as f:
            data = f.read()
    finally:
        os.unlink(path)
    return send_file(
        io.BytesIO(data),
        mimetype="text/csv",
        as_attachment=True,
        download_name="expenses.csv",
    )


@app.route("/sample", methods=["GET"])
def sample_csv():
    """The bundled sample expenses, for trying the import flow."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "samples", "sample-expenses.csv")
    if not os.path.exists(path):
        abort(404, description="The sample file is missing.")
    return send_file(path, mimetype="text/csv", as_attachment=True,
                     download_name="sample-expenses.csv")


@app.route("/chart.png", methods=["GET"])
def chart_png():
    month = parse_month(request.args.get("month"))
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        charts.category_bar_chart(get_conn(), month, path)
        with open(path, "rb") as f:
            data = f.read()
    except ValueError:
        abort(404, description=f"Nothing to chart for {month}.")
    finally:
        os.unlink(path)
    return send_file(io.BytesIO(data), mimetype="image/png")


if __name__ == "__main__":
    app.run(debug=True)
