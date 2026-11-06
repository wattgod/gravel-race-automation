"""Rider-facing generators label pages with the season, not the calendar year.

From September riders plan next year's races, so "Best Gravel Races in
Colorado (2026)" is stale in November 2026. Copyright lines and dated reports
keep the calendar year (shared_footer, generate_legal_pages).
"""

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.append(str(ROOT / "scripts"))

from season import season_year  # noqa: E402

SEASON_MODULES = [
    "generate_calendar",
    "generate_homepage",
    "generate_power_rankings",
    "generate_series_hubs",
    "generate_state_hubs",
    "generate_tire_guide",
    "generate_tire_pages",
    "generate_tire_vs_pages",
    "generate_vs_pages",
    "generate_prep_kit",
]


@pytest.mark.parametrize("name", SEASON_MODULES)
def test_generator_labels_pages_with_the_season(name):
    module = importlib.import_module(name)
    assert str(module.SEASON_YEAR) == str(season_year())


@pytest.mark.parametrize("name", SEASON_MODULES + ["generate_season_roundup"])
def test_generator_does_not_derive_the_year_from_the_calendar(name):
    source = (ROOT / "wordpress" / f"{name}.py").read_text(encoding="utf-8")
    for pattern in ("date.today().year", "datetime.now().year", "CURRENT_YEAR"):
        assert pattern not in source, f"{name}.py uses {pattern}; use season_year()"


def test_copyright_keeps_the_calendar_year():
    from datetime import date

    import shared_footer

    assert shared_footer.CURRENT_YEAR == date.today().year
