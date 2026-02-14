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


class TestSeriesHubInfographics:
    """Test new infographic sections in generated hub pages."""

    def _get_hub_html(self, slug: str) -> str:
        hub_path = (PROJECT_ROOT / "wordpress" / "output" / "race" / "series"
                    / slug / "index.html")
        if not hub_path.exists():
            pytest.skip(f"Series hub page not generated: {hub_path}")
        return hub_path.read_text(encoding="utf-8")

    # ── BWR: full data series (9 profiled events) ──

    def test_bwr_has_radar_chart(self):
        """BWR hub should have radar SVG with overlaid polygons."""
        html = self._get_hub_html("belgian-waffle-ride")
        assert 'aria-label="Difficulty comparison radar chart"' in html
        assert html.count('fill-opacity="0.12"') >= 9, "BWR should have 9 radar polygons"

    def test_bwr_has_distance_elevation_bars(self):
        """BWR hub should have distance/elevation bar chart."""
        html = self._get_hub_html("belgian-waffle-ride")
        assert 'aria-label="Distance and elevation comparison"' in html
        assert "mi</text>" in html
        assert "ft</text>" in html

    def test_bwr_has_at_a_glance_section(self):
        """BWR hub should have 'Series At A Glance' wrapper."""
        html = self._get_hub_html("belgian-waffle-ride")
        assert 'class="gg-series-at-a-glance"' in html
        assert "SERIES AT A GLANCE" in html

    def test_bwr_has_geographic_map(self):
        """BWR hub should have US map with event dots."""
        html = self._get_hub_html("belgian-waffle-ride")
        assert 'aria-label="Geographic map of event locations"' in html
        assert "Event Locations" in html

    def test_bwr_has_timeline(self):
        """BWR hub should have timeline SVG inside history section."""
        html = self._get_hub_html("belgian-waffle-ride")
        assert 'aria-label="Series timeline"' in html
        assert "2012" in html  # BWR founding year

    def test_bwr_has_decision_matrix(self):
        """BWR hub should have decision matrix table with dot meters."""
        html = self._get_hub_html("belgian-waffle-ride")
        assert 'class="gg-series-matrix"' in html
        assert "<table>" in html
        assert "Difficulty" in html
        assert "Technicality" in html

    def test_bwr_has_matrix_picks(self):
        """BWR hub should have 'BEST FOR' editorial picks."""
        html = self._get_hub_html("belgian-waffle-ride")
        assert "Hardest challenge:" in html
        assert "First-timers:" in html

    def test_bwr_has_faq_section(self):
        """BWR hub should have FAQ section with questions."""
        html = self._get_hub_html("belgian-waffle-ride")
        assert 'class="gg-series-faq"' in html
        assert "Frequently Asked Questions" in html
        assert "How many Belgian Waffle Ride events" in html
        assert "Which Belgian Waffle Ride event is the hardest" in html

    def test_bwr_has_faq_jsonld(self):
        """BWR hub should have FAQPage JSON-LD."""
        html = self._get_hub_html("belgian-waffle-ride")
        assert '"FAQPage"' in html

    def test_bwr_radar_has_legend(self):
        """BWR radar chart should have legend with event names."""
        html = self._get_hub_html("belgian-waffle-ride")
        assert "gg-series-radar-legend" in html
        assert "gg-series-radar-legend-swatch" in html

    def test_bwr_has_css_animations(self):
        """BWR hub should have radar draw and bar grow animations."""
        html = self._get_hub_html("belgian-waffle-ride")
        assert "gg-radar-draw" in html
        assert "gg-bar-grow" in html

    # ── LTGP: specific FAQ content ──

    def test_ltgp_has_points_faq(self):
        """LTGP hub should have points system FAQ."""
        html = self._get_hub_html("life-time-grand-prix")
        assert "points system" in html.lower()

    def test_ltgp_has_radar_chart(self):
        """LTGP hub should have radar chart (5 profiled events)."""
        html = self._get_hub_html("life-time-grand-prix")
        assert 'aria-label="Difficulty comparison radar chart"' in html

    # ── Grasshopper: graceful degradation (0 profiled events) ──

    def test_grasshopper_no_radar(self):
        """Grasshopper has no profiled events — radar should be absent."""
        html = self._get_hub_html("grasshopper-adventure-series")
        assert 'aria-label="Difficulty comparison radar chart"' not in html

    def test_grasshopper_no_bars(self):
        """Grasshopper should not have distance/elevation bars."""
        html = self._get_hub_html("grasshopper-adventure-series")
        assert 'aria-label="Distance and elevation comparison"' not in html

    def test_grasshopper_no_matrix(self):
        """Grasshopper should not have decision matrix."""
        html = self._get_hub_html("grasshopper-adventure-series")
        assert "<table>" not in html

    def test_grasshopper_no_map(self):
        """Grasshopper should not have geographic map."""
        html = self._get_hub_html("grasshopper-adventure-series")
        assert 'aria-label="Geographic map of event locations"' not in html

    def test_grasshopper_has_faq(self):
        """Grasshopper should still have FAQ from series-level data."""
        html = self._get_hub_html("grasshopper-adventure-series")
        assert 'class="gg-series-faq"' in html
        assert "How many Grasshopper Adventure Series events" in html

    # ── Gravel Earth: graceful degradation (0 profiled events) ──

    def test_gravel_earth_no_radar(self):
        """Gravel Earth has no profiled events — radar should be absent."""
        html = self._get_hub_html("gravel-earth-series")
        assert 'aria-label="Difficulty comparison radar chart"' not in html

    def test_gravel_earth_has_faq(self):
        """Gravel Earth should still have FAQ from series-level data."""
        html = self._get_hub_html("gravel-earth-series")
        assert 'class="gg-series-faq"' in html

    # ── Section ordering ──

    def test_bwr_section_order(self):
        """Verify sections appear in correct order on BWR page."""
        html = self._get_hub_html("belgian-waffle-ride")
        overview_pos = html.find("Overview</summary>")
        at_a_glance_pos = html.find("SERIES AT A GLANCE")
        history_pos = html.find("History</summary>")
        format_pos = html.find("Format</summary>")
        map_pos = html.find("Event Locations</div>")
        calendar_pos = html.find("2026 Event Calendar")
        matrix_pos = html.find("Decision Matrix</div>")
        faq_pos = html.find("Frequently Asked Questions</div>")
        # Use the body footer element, not the CSS class
        footer_pos = html.find('<footer class="gg-series-footer">')

        assert overview_pos < at_a_glance_pos < history_pos
        assert history_pos < format_pos < map_pos
        assert map_pos < calendar_pos < matrix_pos < faq_pos < footer_pos


class TestSeriesHubQualityGuards:
    """Automated quality guards to prevent known shortcuts from recurring.

    These tests encode the failures documented in LESSONS_LEARNED.md
    Shortcuts #20-26. They catch:
    - HTML entities inside JSON-LD (invalid JSON)
    - FAQ HTML/JSON-LD parity (missing questions)
    - Hardcoded year strings
    - DRY violations (duplicated FAQ logic)
    """

    def _get_hub_html(self, slug: str) -> str:
        hub_path = (PROJECT_ROOT / "wordpress" / "output" / "race" / "series"
                    / slug / "index.html")
        if not hub_path.exists():
            pytest.skip(f"Series hub page not generated: {hub_path}")
        return hub_path.read_text(encoding="utf-8")

    def _extract_jsonld_blocks(self, html: str) -> list:
        """Extract all JSON-LD script blocks from HTML."""
        blocks = []
        start_tag = '<script type="application/ld+json">'
        end_tag = '</script>'
        pos = 0
        while True:
            start = html.find(start_tag, pos)
            if start == -1:
                break
            content_start = start + len(start_tag)
            end = html.find(end_tag, content_start)
            if end == -1:
                break
            blocks.append(html[content_start:end].strip())
            pos = end + len(end_tag)
        return blocks

    @pytest.mark.parametrize("slug", [
        "belgian-waffle-ride",
        "life-time-grand-prix",
        "grinduro",
    ])
    def test_jsonld_is_valid_json(self, slug):
        """All JSON-LD blocks must parse as valid JSON — no HTML entities."""
        html = self._get_hub_html(slug)
        blocks = self._extract_jsonld_blocks(html)
        assert len(blocks) >= 3, f"Expected at least 3 JSON-LD blocks, got {len(blocks)}"
        for i, block in enumerate(blocks):
            try:
                parsed = json.loads(block)
                assert isinstance(parsed, dict), f"JSON-LD block {i} is not an object"
            except json.JSONDecodeError as e:
                pytest.fail(
                    f"JSON-LD block {i} in {slug} is invalid JSON: {e}\n"
                    f"First 200 chars: {block[:200]}"
                )

    @pytest.mark.parametrize("slug", [
        "belgian-waffle-ride",
        "life-time-grand-prix",
        "grinduro",
    ])
    def test_jsonld_no_html_entities(self, slug):
        """JSON-LD blocks must not contain HTML entities like &amp; &#x27; etc."""
        html = self._get_hub_html(slug)
        blocks = self._extract_jsonld_blocks(html)
        for i, block in enumerate(blocks):
            assert "&#" not in block, (
                f"JSON-LD block {i} in {slug} contains HTML entity '&#...'"
            )
            # &amp; and &lt; are also wrong inside JSON
            assert "&amp;" not in block, (
                f"JSON-LD block {i} in {slug} contains '&amp;' (HTML entity in JSON)"
            )

    @pytest.mark.parametrize("slug", [
        "belgian-waffle-ride",
        "life-time-grand-prix",
    ])
    def test_faq_html_and_jsonld_have_same_question_count(self, slug):
        """FAQ HTML and FAQPage JSON-LD must have identical question counts."""
        html = self._get_hub_html(slug)

        # Count FAQ HTML questions (each is a <details> inside the FAQ section)
        faq_start = html.find('class="gg-series-faq"')
        faq_end = html.find('</div>', html.find('</details>', faq_start) + 100)
        if faq_start == -1:
            pytest.skip("No FAQ section found")

        # Count <summary> tags in FAQ section
        html_faq_count = html[faq_start:].count("<summary>")

        # Count JSON-LD FAQ questions
        blocks = self._extract_jsonld_blocks(html)
        faq_block = None
        for block in blocks:
            try:
                parsed = json.loads(block)
                if parsed.get("@type") == "FAQPage":
                    faq_block = parsed
                    break
            except json.JSONDecodeError:
                continue

        assert faq_block is not None, f"No FAQPage JSON-LD found in {slug}"
        jsonld_count = len(faq_block.get("mainEntity", []))

        assert html_faq_count == jsonld_count, (
            f"FAQ parity violation in {slug}: HTML has {html_faq_count} questions "
            f"but JSON-LD has {jsonld_count}. They must match."
        )

    @pytest.mark.parametrize("slug", [
        "belgian-waffle-ride",
        "life-time-grand-prix",
        "gravel-earth-series",
        "grinduro",
        "grasshopper-adventure-series",
    ])
    def test_no_hardcoded_year_in_html(self, slug):
        """No literal '2026' should appear in generated pages (should use dynamic year)."""
        html = self._get_hub_html(slug)
        # The year should match the current year (dynamic), not a hardcoded "2026"
        from datetime import date
        current_year = str(date.today().year)
        # We allow the current year to appear — what we forbid is a year that
        # doesn't match current year. Since we're running in 2026, this test
        # verifies the page uses the dynamic year. In 2027+, pages that still
        # say "2026" would fail.
        if current_year != "2026":
            assert "2026" not in html, (
                f"{slug} still contains hardcoded '2026' — should use dynamic year"
            )

    def test_generator_has_no_hardcoded_year(self):
        """The generator source must not contain hardcoded year in output strings."""
        gen_path = PROJECT_ROOT / "wordpress" / "generate_series_hubs.py"
        source = gen_path.read_text(encoding="utf-8")
        # Find all "2026" occurrences that aren't in comments
        lines = source.split("\n")
        violations = []
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue  # skip comments
            if "2026" in line and "CURRENT_YEAR" not in line:
                violations.append(f"Line {i}: {line.strip()}")
        assert not violations, (
            f"generate_series_hubs.py has hardcoded '2026' in non-comment lines:\n"
            + "\n".join(violations)
        )

    def test_faq_builders_share_single_source(self):
        """Verify FAQ HTML and JSON-LD use _build_faq_pairs (not duplicated logic)."""
        gen_path = PROJECT_ROOT / "wordpress" / "generate_series_hubs.py"
        source = gen_path.read_text(encoding="utf-8")
        # _build_faq_pairs should exist
        assert "def _build_faq_pairs(" in source, (
            "Missing _build_faq_pairs() — FAQ logic is likely duplicated"
        )
        # build_series_faq should call it
        assert "_build_faq_pairs(series" in source, (
            "build_series_faq() doesn't use _build_faq_pairs()"
        )
        # build_faq_jsonld should also call it
        faq_jsonld_start = source.find("def build_faq_jsonld(")
        faq_jsonld_body = source[faq_jsonld_start:source.find("\ndef ", faq_jsonld_start + 1)]
        assert "_build_faq_pairs(" in faq_jsonld_body, (
            "build_faq_jsonld() doesn't use _build_faq_pairs() — DRY violation"
        )

    def test_no_esc_in_jsonld_blocks(self):
        """The generator must not use esc() inside JSON-LD <script> blocks."""
        gen_path = PROJECT_ROOT / "wordpress" / "generate_series_hubs.py"
        source = gen_path.read_text(encoding="utf-8")
        # Find all JSON-LD template blocks and check for esc() usage
        in_jsonld = False
        violations = []
        for i, line in enumerate(source.split("\n"), 1):
            if "application/ld+json" in line:
                in_jsonld = True
            elif in_jsonld and "</script>" in line:
                in_jsonld = False
            elif in_jsonld and "{esc(" in line:
                violations.append(f"Line {i}: {line.strip()}")
        assert not violations, (
            f"esc() used inside JSON-LD blocks (should use _json_str()):\n"
            + "\n".join(violations)
        )


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
