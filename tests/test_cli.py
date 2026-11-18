"""Tests for the CLI argument parsing. Uses the throwaway parser types."""
import argparse

import pytest

import tracker


def test_month_type_accepts_real_months():
    assert tracker.month_type("2026-10") == "2026-10"
    assert tracker.month_type("2027-02") == "2027-02"


def test_month_type_rejects_bad_format():
    with pytest.raises(argparse.ArgumentTypeError):
        tracker.month_type("october")
    with pytest.raises(argparse.ArgumentTypeError):
        tracker.month_type("2026-1")


def test_month_type_rejects_impossible_months():
    # 2026-13 used to pass validation and silently match nothing
    with pytest.raises(argparse.ArgumentTypeError):
        tracker.month_type("2026-13")
    with pytest.raises(argparse.ArgumentTypeError):
        tracker.month_type("2026-00")


def test_date_type_accepts_real_dates():
    assert tracker.date_type("2026-10-04") == "2026-10-04"


def test_date_type_rejects_impossible_dates():
    with pytest.raises(argparse.ArgumentTypeError):
        tracker.date_type("2026-02-30")
    with pytest.raises(argparse.ArgumentTypeError):
        tracker.date_type("2026-13-01")


def test_import_missing_file_is_a_clean_error_not_a_traceback(tmp_path):
    # `tracker.py import nope.csv` used to die with a bare traceback
    args = argparse.Namespace(db=str(tmp_path / "t.db"),
                              file=str(tmp_path / "nope.csv"))
    with pytest.raises(SystemExit, match="no such file"):
        tracker.cmd_import(args)


def test_non_finite_amounts_are_rejected(tmp_path):
    # float() parses "nan"/"inf", and nan <= 0 is False, so both used to
    # be saved -- a NaN expense corrupts every total that touches it.
    db_path = str(tmp_path / "t.db")
    for argv in (["add", "nan", "groceries"], ["add", "inf", "groceries"],
                 ["budget", "set", "groceries", "inf"]):
        with pytest.raises(SystemExit, match="amount must be positive"):
            tracker.main(["--db", db_path] + argv)
    # rejected before any command runs, so the database was never created
    import os
    assert not os.path.exists(db_path)
