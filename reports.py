"""Text reports: monthly summaries and budget checks.

Formatting is done by hand on purpose -- this project started as an excuse
to not pull in tabulate for three columns.
"""
import db


def format_table(headers, rows):
    """Simple left-aligned table. Returns a list of lines."""
    widths = [len(h) for h in headers]
    str_rows = [[str(cell) for cell in row] for row in rows]
    for row in str_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt(row):
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip()

    lines = [fmt(headers)]
    lines.append("-" * max(len(fmt(headers)), 1))
    lines.extend(fmt(r) for r in str_rows)
    return lines


def money(amount):
    return f"${amount:,.2f}"


def summary(conn, month):
    """Per-category totals plus a grand total, as a printable string."""
    totals = db.category_totals(conn, month)
    lines = [f"Spending - {month}", ""]
    if not totals:
        lines.append("No expenses recorded.")
        return "\n".join(lines)
    rows = [(cat, money(total)) for cat, total in totals]
    lines.extend(format_table(["category", "total"], rows))
    lines.append("")
    lines.append(f"Grand total: {money(db.grand_total(conn, month))}")
    return "\n".join(lines)


def budget_status(spent, limit):
    """One-word verdict used by budget_check()."""
    if limit <= 0:
        return "n/a"
    pct = spent / limit
    if pct >= 1.0:
        return "OVER"
    if pct >= 0.8:
        return "WARNING"
    return "ok"


def budget_check(conn, month):
    """Compare this month's spending against each budget.

    Flags a category once it passes 80% of its budget, and again when it
    goes over. Categories with a budget but no spending this month still
    show up so you remember they exist.
    """
    budgets = db.get_budgets(conn)
    lines = [f"Budgets - {month}", ""]
    if not budgets:
        lines.append("No budgets set. Use: tracker.py budget set <category> <amount>")
        return "\n".join(lines)

    spent_by_cat = dict(db.category_totals(conn, month))
    rows = []
    for category, limit in budgets:
        spent = spent_by_cat.get(category, 0.0)
        pct = (spent / limit * 100) if limit else 0.0
        rows.append((category, money(spent), money(limit), f"{pct:.0f}%", budget_status(spent, limit)))
    lines.extend(format_table(["category", "spent", "budget", "used", "status"], rows))
    return "\n".join(lines)


# TODO: recurring expenses -- flag subscriptions (netflix, spotify, rent)
# that appear every month so they don't surprise the budget check.
