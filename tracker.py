#!/usr/bin/env python3
"""expense-tracker: log and review spending from the terminal.

Examples:
    python tracker.py add 12.50 groceries --note "weekly run"
    python tracker.py add 1450 rent --date 2026-10-01
    python tracker.py summary --month 2026-10
    python tracker.py budget set groceries 400
    python tracker.py budget check
"""
import argparse
import datetime
import re
import sys

import charts
import db
import reports


def month_type(value):
    if not re.fullmatch(r"\d{4}-\d{2}", value):
        raise argparse.ArgumentTypeError("month must look like 2026-10")
    return value


def date_type(value):
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError("date must look like 2026-10-04")


def current_month():
    return datetime.date.today().strftime("%Y-%m")


# --- subcommand handlers -------------------------------------------------

def cmd_add(args):
    conn = db.connect(args.db)
    day = args.date or datetime.date.today().isoformat()
    exp_id = db.add_expense(conn, args.amount, args.category, args.note, day)
    note = f" ({args.note})" if args.note else ""
    print(f"#{exp_id}  ${args.amount:.2f} [{args.category}] {day}{note}")


def cmd_list(args):
    conn = db.connect(args.db)
    rows = db.list_expenses(conn, month=args.month, category=args.category)
    if not rows:
        print("No expenses found.")
        return
    table = [(r["id"], r["date"], r["category"], f"${r['amount']:.2f}", r["note"]) for r in rows]
    print("\n".join(reports.format_table(["id", "date", "category", "amount", "note"], table)))


def cmd_summary(args):
    conn = db.connect(args.db)
    print(reports.summary(conn, args.month))


def cmd_budget_set(args):
    conn = db.connect(args.db)
    db.set_budget(conn, args.category, args.amount)
    print(f"Budget for '{args.category}': ${args.amount:.2f}/month")


def cmd_budget_check(args):
    conn = db.connect(args.db)
    print(reports.budget_check(conn, args.month))


def cmd_import(args):
    conn = db.connect(args.db)
    imported, skipped = db.import_csv(conn, args.file)
    msg = f"Imported {imported} expense(s) from {args.file}."
    if skipped:
        msg += f" Skipped {skipped} bad row(s)."
    print(msg)


def cmd_export(args):
    conn = db.connect(args.db)
    count = db.export_csv(conn, args.file)
    print(f"Wrote {count} expense(s) to {args.file}.")


def cmd_chart(args):
    conn = db.connect(args.db)
    out = args.out or f"spending-{args.month}.png"
    try:
        charts.category_bar_chart(conn, args.month, out)
    except ValueError as e:
        sys.exit(f"error: {e}")
    print(f"Saved chart to {out}")


# --- parser --------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="tracker.py",
        description="Track personal spending from the command line.",
    )
    parser.add_argument(
        "--db",
        default=db.default_db_path(),
        help="sqlite database file (default: expenses.db, or $EXPENSE_DB)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add", help="log a new expense")
    p.add_argument("amount", type=float, help="how much you spent")
    p.add_argument("category", help="e.g. groceries, rent, coffee")
    p.add_argument("--note", default="", help="optional memo")
    p.add_argument("--date", type=date_type, default=None, help="YYYY-MM-DD (default: today)")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("list", help="show recorded expenses")
    p.add_argument("--month", type=month_type, default=None, help="filter by YYYY-MM")
    p.add_argument("--category", default=None, help="filter by category")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("summary", help="per-category totals for a month")
    p.add_argument("--month", type=month_type, default=current_month())
    p.set_defaults(func=cmd_summary)

    p = sub.add_parser("budget", help="monthly budgets")
    bsub = p.add_subparsers(dest="budget_cmd", required=True)
    s = bsub.add_parser("set", help="set a monthly budget for a category")
    s.add_argument("category")
    s.add_argument("amount", type=float)
    s.set_defaults(func=cmd_budget_set)
    c = bsub.add_parser("check", help="compare this month's spending to budgets")
    c.add_argument("--month", type=month_type, default=current_month())
    c.set_defaults(func=cmd_budget_check)

    p = sub.add_parser("import", help="load expenses from a CSV file")
    p.add_argument("file")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("export", help="dump all expenses to a CSV file")
    p.add_argument("file")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("chart", help="save a bar chart of spending by category")
    p.add_argument("--month", type=month_type, default=current_month())
    p.add_argument("--out", default=None, help="output PNG path (default: spending-YYYY-MM.png)")
    p.set_defaults(func=cmd_chart)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    amount = getattr(args, "amount", None)
    if amount is not None and amount <= 0:
        sys.exit("error: amount must be positive")
    args.func(args)


if __name__ == "__main__":
    main()
