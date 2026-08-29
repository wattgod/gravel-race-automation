"""Regression tests for GA4 output classification."""

from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_preflight_quality():
    path = PROJECT_ROOT / "scripts" / "preflight_quality.py"
    spec = importlib.util.spec_from_file_location("preflight_quality_ga4_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_private_noindex_nofollow_pages_are_exempt_regardless_of_spacing_or_order():
    preflight = _load_preflight_quality()

    assert preflight._is_internal_noindex_nofollow(
        '<meta name="robots" content="noindex,nofollow">'
    )
    assert preflight._is_internal_noindex_nofollow(
        "<meta content='nofollow, noindex' name='robots'>"
    )
    assert preflight._is_internal_noindex_nofollow(
        '<META NAME="ROBOTS" CONTENT="NOINDEX, NOFOLLOW">'
    )


def test_public_or_indexable_pages_are_not_exempt_from_ga4_coverage():
    preflight = _load_preflight_quality()

    assert not preflight._is_internal_noindex_nofollow(
        '<meta name="robots" content="index,follow">'
    )
    assert not preflight._is_internal_noindex_nofollow(
        '<meta name="robots" content="noindex,follow">'
    )
    assert not preflight._is_internal_noindex_nofollow(
        '<p>Internal note: noindex,nofollow</p>'
    )
