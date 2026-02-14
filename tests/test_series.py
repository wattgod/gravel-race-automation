"""
Tests for series hub pages and series data integrity.

Validates:
1. Series data files parse correctly with required fields
2. Series-race cross-references are consistent
3. Series hub HTML pages have correct structure
4. Race profiles with series show badge and breadcrumb
5. Index entries inherit series fields
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERIES_DIR = PROJECT_ROOT / "series-data"
RACE_DIR = PROJECT_ROOT / "race-data"
INDEX_PATH = PROJECT_ROOT / "web" / "race-index.json"

# Required fields in every series definition
REQUIRED_SERIES_FIELDS = {"name", "slug", "display_name", "events"}
REQUIRED_EVENT_FIELDS = {"name", "has_profile"}


# ── Series Data Integrity ──────────────────────────────────────


def get_series_files():
    """Get all series JSON files."""
    if not SERIES_DIR.exists():
        return []
    return sorted(SERIES_DIR.glob("*.json"))


def load_series(path):
    """Load a series definition file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("series", {})


@pytest.fixture
def all_series():
    """Load all series definitions."""
    return [(p, load_series(p)) for p in get_series_files()]


@pytest.fixture
def race_index():
    """Load race index."""
    if not INDEX_PATH.exists():
        return []
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TestSeriesDataIntegrity:
    """Ensure all series-data/*.json files are valid."""

    def test_series_dir_exists(self):
        assert SERIES_DIR.exists(), f"series-data/ directory not found at {SERIES_DIR}"

    def test_series_files_parse_as_json(self):
        for path in get_series_files():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"{path.name} is not valid JSON: {e}")

    def test_series_have_required_fields(self, all_series):
        for path, series in all_series:
            missing = REQUIRED_SERIES_FIELDS - set(series.keys())
            assert not missing, f"{path.name} missing fields: {missing}"

    def test_series_events_have_required_fields(self, all_series):
        for path, series in all_series:
            for i, event in enumerate(series.get("events", [])):
                missing = REQUIRED_EVENT_FIELDS - set(event.keys())
                assert not missing, (
                    f"{path.name} event[{i}] ({event.get('name', '?')}) "
                    f"missing fields: {missing}"
                )

    def test_no_duplicate_series_slugs(self, all_series):
        slugs = [s.get("slug") for _, s in all_series]
        dupes = [slug for slug in slugs if slugs.count(slug) > 1]
        assert not dupes, f"Duplicate series slugs: {set(dupes)}"

    def test_profiled_events_have_race_files(self, all_series):
        """Every event with has_profile=True must have a matching race-data/{slug}.json."""
        for path, series in all_series:
            for event in series.get("events", []):
                if event.get("has_profile") and event.get("slug"):
                    race_file = RACE_DIR / f"{event['slug']}.json"
                    assert race_file.exists(), (
                        f"{path.name}: event '{event['name']}' has has_profile=True "
                        f"but {race_file.name} does not exist"
                    )


class TestSeriesCrossReferences:
    """Ensure race-data files correctly reference series-data and vice versa."""

    def test_tagged_races_reference_existing_series(self):
        """Every race with a 'series' field should point to an existing series-data file."""
        if not RACE_DIR.exists():
            pytest.skip("race-data/ not found")

        series_ids = set()
        for path in get_series_files():
            series = load_series(path)
            series_ids.add(series.get("slug", ""))

        for race_file in sorted(RACE_DIR.glob("*.json")):
            with open(race_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            race = data.get("race", {})
            series_ref = race.get("series", {})
            if series_ref.get("id"):
                assert series_ref["id"] in series_ids, (
                    f"{race_file.name} references series '{series_ref['id']}' "
                    f"which does not exist in series-data/"
                )

    def test_series_event_slugs_match_race_files(self, all_series):
        """Series event slugs should match actual race files when has_profile is True."""
        for path, series in all_series:
            for event in series.get("events", []):
                slug = event.get("slug")
                if slug and event.get("has_profile"):
                    race_file = RACE_DIR / f"{slug}.json"
                    assert race_file.exists(), (
                        f"{path.name}: event slug '{slug}' has no matching race file"
                    )


class TestSeriesIndexIntegration:
    """Ensure index entries inherit series fields correctly."""

    def test_tagged_races_have_series_in_index(self, race_index):
        """Races that belong to a series should have series_id/series_name in the index."""
        if not race_index:
            pytest.skip("race-index.json not found or empty")

        # Load series data to get expected tagged slugs
        expected_series_slugs = {}
        for path in get_series_files():
            series = load_series(path)
            series_id = series.get("slug", "")
            for event in series.get("events", []):
                if event.get("slug") and event.get("has_profile"):
                    expected_series_slugs[event["slug"]] = series_id

        index_by_slug = {r["slug"]: r for r in race_index if r.get("slug")}

        for race_slug, series_id in expected_series_slugs.items():
            if race_slug in index_by_slug:
                entry = index_by_slug[race_slug]
                assert entry.get("series_id") == series_id, (
                    f"Index entry '{race_slug}' should have series_id='{series_id}' "
                    f"but has '{entry.get('series_id')}'"
                )


class TestSeriesHubPages:
    """Test generated series hub HTML pages."""

    def _get_hub_html(self, slug: str) -> str:
        hub_path = (PROJECT_ROOT / "wordpress" / "output" / "race" / "series"
                    / slug / "index.html")
        if not hub_path.exists():
            pytest.skip(f"Series hub page not generated: {hub_path}")
        return hub_path.read_text(encoding="utf-8")

    @pytest.mark.parametrize("slug", [
        "belgian-waffle-ride",
        "life-time-grand-prix",
        "gravel-earth-series",
        "grinduro",
        "grasshopper-adventure-series",
    ])
    def test_hub_page_exists(self, slug):
        hub_path = (PROJECT_ROOT / "wordpress" / "output" / "race" / "series"
                    / slug / "index.html")
        assert hub_path.exists(), f"Missing series hub page: {hub_path}"

    @pytest.mark.parametrize("slug", [
        "belgian-waffle-ride",
        "life-time-grand-prix",
        "gravel-earth-series",
        "grinduro",
        "grasshopper-adventure-series",
    ])
    def test_hub_has_site_header(self, slug):
        html = self._get_hub_html(slug)
        assert "gg-site-header" in html
        assert "gg-site-header-logo" in html
        assert "/gravel-races/" in html
        assert "/coaching/" in html
        assert "/articles/" in html
        assert "/about/" in html

    @pytest.mark.parametrize("slug", [
        "belgian-waffle-ride",
        "life-time-grand-prix",
        "gravel-earth-series",
        "grinduro",
        "grasshopper-adventure-series",
    ])
    def test_hub_has_event_cards(self, slug):
        html = self._get_hub_html(slug)
        assert "gg-series-event-card" in html

    def test_bwr_hub_has_9_event_cards(self):
        html = self._get_hub_html("belgian-waffle-ride")
        count = html.count("gg-series-event-card")
        # Each card has the class in the div, some CSS may also match
        assert count >= 9, f"BWR hub should have at least 9 event cards, found {count}"

    @pytest.mark.parametrize("slug", [
        "belgian-waffle-ride",
        "life-time-grand-prix",
        "gravel-earth-series",
        "grinduro",
        "grasshopper-adventure-series",
    ])
    def test_hub_has_json_ld(self, slug):
        html = self._get_hub_html(slug)
        assert "application/ld+json" in html
        assert "SportsOrganization" in html
        assert "BreadcrumbList" in html
        assert "ItemList" in html

    @pytest.mark.parametrize("slug", [
        "belgian-waffle-ride",
        "life-time-grand-prix",
        "gravel-earth-series",
        "grinduro",
        "grasshopper-adventure-series",
    ])
    def test_hub_has_breadcrumb(self, slug):
        html = self._get_hub_html(slug)
        assert "gg-series-breadcrumb" in html
        assert "Gravel Races" in html
        assert "Series" in html


class TestRaceProfileSeriesIntegration:
    """Test that race profiles with series show badge and breadcrumb."""

    def test_series_badge_in_hero(self):
        """BWR California should show series badge in hero."""
        sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
        from generate_neo_brutalist import load_race_data, build_hero

        rd = load_race_data(RACE_DIR / "bwr-california.json")
        hero = build_hero(rd)
        assert "gg-series-badge" in hero
        assert "belgian-waffle-ride" in hero
        assert "BELGIAN WAFFLE RIDE SERIES" in hero

    def test_series_in_breadcrumb(self):
        """BWR California breadcrumb should include series segment."""
        sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
        from generate_neo_brutalist import load_race_data, build_nav_header

        rd = load_race_data(RACE_DIR / "bwr-california.json")
        nav = build_nav_header(rd, [])
        assert "/race/series/belgian-waffle-ride/" in nav
        assert "Belgian Waffle Ride Series" in nav

    def test_non_series_race_has_tier_breadcrumb(self):
        """A race without series should still show tier in breadcrumb."""
        sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
        from generate_neo_brutalist import load_race_data, build_nav_header

        rd = load_race_data(RACE_DIR / "mid-south.json")
        nav = build_nav_header(rd, [])
        assert "tier-" in nav
        assert "gg-series-badge" not in build_hero_safe(rd)

    def test_no_series_badge_on_non_series_race(self):
        """Non-series race should not show series badge."""
        sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
        from generate_neo_brutalist import load_race_data, build_hero

        rd = load_race_data(RACE_DIR / "mid-south.json")
        hero = build_hero(rd)
        assert "gg-series-badge" not in hero


def build_hero_safe(rd):
    """Import and call build_hero safely."""
    sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
    from generate_neo_brutalist import build_hero
    return build_hero(rd)
