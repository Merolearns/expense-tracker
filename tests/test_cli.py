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
