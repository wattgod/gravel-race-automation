"""Tests for scripts/daily-marketing-report.py — GSC window lag handling.

The module filename has a dash, so it can't be imported as a normal
dotted module; load it directly from its file path instead.
"""
from __future__ import annotations

import importlib.util
import os
from datetime import timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = PROJECT_ROOT / "scripts" / "daily-marketing-report.py"

spec = importlib.util.spec_from_file_location("daily_marketing_report", MODULE_PATH)
daily_marketing_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daily_marketing_report)


def test_gsc_windows_are_fully_lagged_and_equal_length():
    """Both the current and previous 7-day GSC windows must end at least
    GSC_LAG_DAYS before today, and be the same length as each other —
    otherwise the comparison mixes a partially-processed window against a
    fully-settled one and always reads as a decline (see intel finding
    2026-09-02: every daily report for weeks showed a -20% to -45% WoW
    'decline' in Search Performance purely from this mismatch).
    """
    today = daily_marketing_report.CURRENT_DATE - timedelta(
        days=daily_marketing_report.GSC_LAG_DAYS
    )
    seven_ago = today - timedelta(days=7)
    fourteen_ago = today - timedelta(days=14)

    assert (daily_marketing_report.CURRENT_DATE - today).days == (
        daily_marketing_report.GSC_LAG_DAYS
    )
    assert (today - seven_ago).days == 7
    assert (seven_ago - fourteen_ago).days == 7


def test_fetch_gsc_data_returns_none_without_credentials():
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    assert daily_marketing_report.fetch_gsc_data() is None
