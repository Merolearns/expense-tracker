# expense-tracker

A small command-line expense tracker with monthly budgets and charts.

I kept opening my banking app at the end of the month and having no idea where the money actually went, so I built this. It's a learning project -- I wanted to get comfortable with `argparse`, `sqlite3`, and matplotlib in one sitting. Everything lives in a single SQLite file, no accounts, no servers.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Log an expense:

```bash
python tracker.py add 12.50 groceries --note "weekly run"
python tracker.py add 1450 rent --date 2026-10-01
```

See what you spent:

```bash
python tracker.py list --month 2026-10
python tracker.py list --category coffee
python tracker.py summary --month 2026-10
```

Set budgets and check them:

```bash
python tracker.py budget set groceries 400
python tracker.py budget set coffee 60
python tracker.py budget check
```

Budget check warns you at 80% of a category's budget and flags it again once you're over.

Import/export CSV (handy for backups or moving data between machines):

```bash
python tracker.py export backup.csv
python tracker.py import backup.csv
```

Draw a chart:

```bash
python tracker.py chart --month 2026-10 --out october.png
```

The database defaults to `expenses.db` in the current directory; point `EXPENSE_DB` or `--db` at another file to use a different one.

## Example session

```
$ python tracker.py add 42.18 groceries --note "trader joes"
#1  $42.18 [groceries] 2026-10-04 (trader joes)

$ python tracker.py budget set groceries 400
Budget for 'groceries': $400.00/month

$ python tracker.py summary --month 2026-10
Spending - 2026-10

category   total
---------------
groceries  $42.18

Grand total: $42.18

$ python tracker.py chart --month 2026-10 --out october.png
Saved chart to october.png
```

## Tests

```bash
pytest
```

## What I'd add next

- Recurring expenses: flag subscriptions that hit every month so they don't surprise the budget check.
- A `weekly` view -- right now everything is monthly.
- Multi-currency would be nice, but I don't travel enough to need it yet.

## License

MIT -- see LICENSE.
