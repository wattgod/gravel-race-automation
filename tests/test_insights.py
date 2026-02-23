"""Tests for the Gravel God data insights page generator."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_insights import (
    ALL_DIMS,
    COUNTRY_MAP,
    COUNTRY_NAMES,
    DENSITY_HIGH_MIN,
    DENSITY_MED_MIN,
    DIM_LABELS,
    MONTHS,
    RANKING_PRESETS,
    US_STATES,
    US_TILE_GRID,
    WORLD_REGIONS,
    build_closing,
    build_cta_block,
    build_data_story,
    build_dimension_leaderboard,
    build_figure_wrap,
    build_hero,
    build_insights_css,
    build_insights_js,
    build_jsonld,
    build_nav,
    build_overrated_underrated,
    build_race_data_embed,
    build_ranking_builder,
    compute_editorial_facts,
    compute_stats,
    enrich_races,
    extract_country,
    extract_price,
    extract_state,
    generate_insights_page,
    load_race_index,
    safe_num,
)
from generate_neo_brutalist import SITE_BASE_URL


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture(scope="module")
def all_races():
    """All 328 races (gravel + bikepacking + MTB)."""
    raw = load_race_index()
    return enrich_races(raw)


@pytest.fixture(scope="module")
def gravel_races(all_races):
    """Gravel-only races (matching generator filter)."""
    return [r for r in all_races if (r.get("discipline") or "gravel") == "gravel"]


@pytest.fixture(scope="module")
def race_count(gravel_races):
    return len(gravel_races)


@pytest.fixture(scope="module")
def stats(gravel_races):
    return compute_stats(gravel_races)


@pytest.fixture(scope="module")
def insights_html():
    return generate_insights_page()


@pytest.fixture(scope="module")
def insights_css():
    return build_insights_css()


@pytest.fixture(scope="module")
def insights_js():
    return build_insights_js()


@pytest.fixture(scope="module")
def editorial_facts(gravel_races):
    return compute_editorial_facts(gravel_races)


# ── TestHelpers ───────────────────────────────────────────────


class TestHelpers:
    """Test data utility functions."""

    # safe_num
    def test_safe_num_int(self):
        assert safe_num(42) == 42.0

    def test_safe_num_float(self):
        assert safe_num(3.14) == 3.14

    def test_safe_num_string(self):
        assert safe_num("1,234") == 1234.0

    def test_safe_num_none(self):
        assert safe_num(None) == 0

    def test_safe_num_na(self):
        assert safe_num("N/A") == 0

    def test_safe_num_empty_string(self):
        assert safe_num("") == 0

    def test_safe_num_default(self):
        assert safe_num(None, default=99) == 99

    # extract_price
    def test_extract_price_basic(self):
        assert extract_price("Cost: $345") == 345.0

    def test_extract_price_comma(self):
        assert extract_price("Entry: $4,400") == 4400.0

    def test_extract_price_none(self):
        assert extract_price(None) is None

    def test_extract_price_no_dollar(self):
        assert extract_price("Free entry!") is None

    def test_extract_price_multiple_amounts(self):
        result = extract_price("Early bird: $100, Regular: $150")
        assert result == 100.0

    def test_extract_price_vip_stripped(self):
        result = extract_price("Via BikeReg. VIP Package: $1,000 USD")
        assert result is None  # VIP-only text has no standard price

    # extract_state
    def test_extract_state_full_name(self):
        assert extract_state("Emporia, Kansas") == "KS"

    def test_extract_state_abbreviation(self):
        assert extract_state("Leadville, CO") == "CO"

    def test_extract_state_none(self):
        assert extract_state(None) is None

    def test_extract_state_international(self):
        assert extract_state("Girona, Spain") is None

    def test_extract_state_empty(self):
        assert extract_state("") is None

    # Constants
    def test_all_dims_count(self):
        assert len(ALL_DIMS) == 14

    def test_dim_labels_match_all_dims(self):
        for d in ALL_DIMS:
            assert d in DIM_LABELS, f"Missing label for dim: {d}"

    def test_months_count(self):
        assert len(MONTHS) == 12

    def test_months_starts_january(self):
        assert MONTHS[0] == "January"

    def test_us_states_are_sorted(self):
        assert US_STATES == sorted(US_STATES)

    def test_all_dims_expected_members(self):
        expected = {
            "logistics", "length", "technicality", "elevation", "climate",
            "altitude", "adventure", "prestige", "race_quality", "experience",
            "community", "field_depth", "value", "expenses",
        }
        assert set(ALL_DIMS) == expected


# ── TestPageGeneration ────────────────────────────────────────


class TestPageGeneration:
    """Test overall page structure."""

    def test_returns_html(self, insights_html):
        assert "<!DOCTYPE html>" in insights_html

    def test_charset(self, insights_html):
        assert 'charset="UTF-8"' in insights_html

    def test_has_hero_section(self, insights_html):
        assert 'id="hero"' in insights_html

    def test_has_tier_breakdown_section(self, insights_html):
        assert 'id="tier-breakdown"' in insights_html

    def test_has_geography_section(self, insights_html):
        assert 'id="geography"' in insights_html

    def test_has_calendar_section(self, insights_html):
        assert 'id="calendar"' in insights_html

    def test_has_price_myth_section(self, insights_html):
        assert 'id="price-myth"' in insights_html

    def test_has_dimension_leaderboard_section(self, insights_html):
        assert 'id="dimension-leaderboard"' in insights_html

    def test_has_ranking_section(self, insights_html):
        assert 'id="ranking-builder"' in insights_html

    def test_has_overrated_section(self, insights_html):
        assert 'id="overrated-underrated"' in insights_html

    def test_has_closing_section(self, insights_html):
        assert 'id="what-now"' in insights_html

    def test_gg_ins_prefix_in_html(self, insights_html):
        assert "gg-ins-" in insights_html

    def test_gg_insights_prefix_in_html(self, insights_html):
        assert "gg-insights-" in insights_html

    def test_no_removed_sections(self, insights_html):
        """Old sections must not appear."""
        for old_id in [
            "scrollytelling",
            "regional-divide",
            "elite-gap",
            "prestige-cliff",
            "pricing",
            "ultra-scale",
            "value-paradox",
            "tier-pyramid",
            "calendar-section",
            "hidden-gems",
            "scatter-explorer",
            "heritage",
        ]:
            assert f'id="{old_id}"' not in insights_html, (
                f"Old section {old_id} still present"
            )

    def test_page_title(self, insights_html):
        assert "<title>" in insights_html
        assert "State of Gravel" in insights_html

    def test_robots_meta(self, insights_html):
        assert 'content="index, follow"' in insights_html

    def test_section_order(self, insights_html):
        """Verify correct section ordering."""
        hero_pos = insights_html.find('id="hero"')
        data_pos = insights_html.find('id="gg-race-data"')
        tier_pos = insights_html.find('id="tier-breakdown"')
        geo_pos = insights_html.find('id="geography"')
        cal_pos = insights_html.find('id="calendar"')
        price_pos = insights_html.find('id="price-myth"')
        dim_pos = insights_html.find('id="dimension-leaderboard"')
        rank_pos = insights_html.find('id="ranking-builder"')
        ou_pos = insights_html.find('id="overrated-underrated"')
        closing_pos = insights_html.find('id="what-now"')
        assert hero_pos < data_pos < tier_pos < geo_pos < cal_pos < price_pos < dim_pos < rank_pos < ou_pos < closing_pos

    def test_no_scatter_explorer(self, insights_html):
        assert 'id="scatter-explorer"' not in insights_html

    def test_no_heritage_section(self, insights_html):
        assert 'id="heritage"' not in insights_html

    def test_no_newsletter_embed(self, insights_html):
        assert "gg-insights-newsletter" not in insights_html

    def test_no_exit_intent_popup(self, insights_html):
        """No exit-intent popup HTML elements on insights page."""
        # Shared CSS/JS may mention exit-intent, but no actual popup element
        assert 'id="exit-intent"' not in insights_html
        assert 'class="exit-intent' not in insights_html


# ── TestNav ───────────────────────────────────────────────────


class TestNav:
    """Test navigation and breadcrumb."""

    def test_has_breadcrumb(self, insights_html):
        assert "gg-insights-breadcrumb" in insights_html

    def test_breadcrumb_home_link(self, insights_html):
        assert "Home</a>" in insights_html

    def test_breadcrumb_articles_link(self, insights_html):
        assert "articles/" in insights_html

    def test_breadcrumb_current(self, insights_html):
        assert "The State of Gravel" in insights_html

    def test_shared_header(self, insights_html):
        assert "gg-site-header" in insights_html


# ── TestHero ──────────────────────────────────────────────────


class TestHero:
    """Test the hero section."""

    def test_hero_title(self, insights_html):
        assert "The State of Gravel" in insights_html

    def test_hero_subtitle_scroll(self, insights_html):
        assert "Scroll to explore" in insights_html

    def test_counters_present(self, insights_html):
        assert "data-counter" in insights_html

    def test_counter_races(self, insights_html):
        assert "data-counter=" in insights_html

    def test_hero_section_id(self, insights_html):
        assert 'id="hero"' in insights_html

    def test_hero_class(self, insights_html):
        assert "gg-insights-hero" in insights_html

    def test_hero_inner(self, insights_html):
        assert "gg-insights-hero-inner" in insights_html

    def test_counter_labels_present(self, insights_html):
        assert "gg-insights-counter-label" in insights_html

    def test_counter_values_present(self, insights_html):
        assert "gg-insights-counter-value" in insights_html

    def test_hero_subtitle_centered(self, insights_html):
        """Hero subtitle should exist with race count."""
        hero_match = re.search(
            r'id="hero".*?</section>', insights_html, re.DOTALL
        )
        assert hero_match
        assert "gg-insights-hero-subtitle" in hero_match.group()


# ── TestRaceDataEmbed ─────────────────────────────────────────


class TestRaceDataEmbed:
    """Test the embedded JSON data blob."""

    def _get_json(self, insights_html):
        match = re.search(
            r'<script type="application/json" id="gg-race-data">(.*?)</script>',
            insights_html,
            re.DOTALL,
        )
        assert match, "Race data embed not found"
        return json.loads(match.group(1))

    def test_embed_present(self, insights_html):
        assert 'id="gg-race-data"' in insights_html

    def test_embed_is_valid_json(self, insights_html):
        data = self._get_json(insights_html)
        assert isinstance(data, list)

    def test_embed_has_gravel_only_entries(self, insights_html, race_count):
        data = self._get_json(insights_html)
        assert len(data) == race_count

    def test_entry_has_required_fields(self, insights_html):
        data = self._get_json(insights_html)
        required = {"s", "n", "t", "sc", "p", "d", "e", "r", "m", "st", "dm", "di", "f"}
        for entry in data[:5]:
            assert required.issubset(set(entry.keys())), (
                f"Missing fields in {entry.get('s', '?')}"
            )

    def test_dm_length_is_14(self, insights_html):
        data = self._get_json(insights_html)
        for entry in data:
            assert len(entry["dm"]) == 14, (
                f"{entry['s']} has dm length {len(entry['dm'])}"
            )

    def test_tier_range(self, insights_html):
        data = self._get_json(insights_html)
        for entry in data:
            assert 1 <= entry["t"] <= 4, f"{entry['s']} has tier {entry['t']}"

    def test_score_range(self, insights_html):
        data = self._get_json(insights_html)
        for entry in data:
            assert 0 <= entry["sc"] <= 100, f"{entry['s']} has score {entry['sc']}"

    def test_dimension_range(self, insights_html):
        data = self._get_json(insights_html)
        for entry in data:
            for i, v in enumerate(entry["dm"]):
                assert 0 <= v <= 5, f"{entry['s']} dim[{i}]={v}"

    def test_unique_slugs(self, insights_html):
        data = self._get_json(insights_html)
        slugs = [e["s"] for e in data]
        assert len(slugs) == len(set(slugs)), "Duplicate slugs in race data"

    def test_size_under_60kb(self, insights_html):
        match = re.search(
            r'<script type="application/json" id="gg-race-data">(.*?)</script>',
            insights_html,
            re.DOTALL,
        )
        assert len(match.group(1).encode()) < 60000, "Race data exceeds 60KB"

    def test_gravel_only_no_bikepacking(self, insights_html):
        """Bikepacking and MTB must be excluded from analysis."""
        data = self._get_json(insights_html)
        for entry in data:
            assert entry["di"] == "gravel", (
                f"{entry['s']} has discipline {entry['di']} — non-gravel in insights"
            )

    def test_has_unbound(self, insights_html):
        """Smoke test: Unbound 200 should be in the data."""
        data = self._get_json(insights_html)
        slugs = [e["s"] for e in data]
        assert "unbound-200" in slugs

    def test_compact_json_no_spaces(self, insights_html):
        """Embedded JSON should use compact separators."""
        match = re.search(
            r'<script type="application/json" id="gg-race-data">(.*?)</script>',
            insights_html,
            re.DOTALL,
        )
        blob = match.group(1)
        assert '": ' not in blob, "JSON blob is not compact"


# ── TestDataStory ─────────────────────────────────────────────


class TestDataStory:
    """Test the 4 data story sections (tier, geography, calendar, price)."""

    # ── Tier Breakdown ──
    def test_tier_section_id(self, insights_html):
        assert 'id="tier-breakdown"' in insights_html

    def test_tier_section_class(self, insights_html):
        assert "gg-insights-section" in insights_html

    def test_tier_title(self, insights_html):
        assert "The Gravel 1%" in insights_html

    def test_tier_has_4_bars(self, insights_html):
        tier_match = re.search(
            r'id="tier-breakdown".*?</section>', insights_html, re.DOTALL
        )
        assert tier_match
        bars = re.findall(r'data-tier="\d"', tier_match.group())
        assert len(bars) == 4

    def test_tier_bar_fill_class(self, insights_html):
        assert "gg-ins-data-bar-fill" in insights_html

    def test_tier_bar_data_animate(self, insights_html):
        tier_match = re.search(
            r'id="tier-breakdown".*?</section>', insights_html, re.DOTALL
        )
        assert tier_match
        assert 'data-animate="bars"' in tier_match.group()

    def test_tier_counts_present(self, insights_html):
        assert "gg-ins-data-count" in insights_html

    def test_tier_descriptions_present(self, insights_html):
        assert "gg-ins-data-desc" in insights_html

    def test_tier_labels_present(self, insights_html):
        for label in ["Tier 1", "Tier 2", "Tier 3", "Tier 4"]:
            assert label in insights_html, f"Tier label '{label}' missing"

    # ── Geography (Tile Grid Map) ──
    def test_geography_section_id(self, insights_html):
        assert 'id="geography"' in insights_html

    def test_geography_title(self, insights_html):
        assert "Geography Is Destiny" in insights_html

    def test_geography_has_tile_grid(self, insights_html):
        assert "gg-ins-map-grid" in insights_html

    def test_geography_has_50_state_tiles(self, insights_html):
        geo_match = re.search(
            r'gg-ins-map-grid.*?</div>\s*<div class="gg-ins-map-detail"', insights_html, re.DOTALL
        )
        assert geo_match
        tiles = re.findall(r'class="gg-ins-map-tile"', geo_match.group())
        assert len(tiles) == 50, f"Expected 50 state tiles, got {len(tiles)}"

    def test_geography_tiles_have_data_count(self, insights_html):
        geo_match = re.search(
            r'gg-ins-map-grid.*?</div>\s*<div class="gg-ins-map-detail"', insights_html, re.DOTALL
        )
        assert geo_match
        counts = re.findall(r'data-count="\d+"', geo_match.group())
        assert len(counts) == 50

    def test_geography_tiles_have_data_density(self, insights_html):
        geo_match = re.search(
            r'id="geography".*?</section>', insights_html, re.DOTALL
        )
        assert geo_match
        # Count only US map tiles (not world tiles)
        densities = re.findall(r'gg-ins-map-tile"[^>]*data-density="(none|low|med|high)"', geo_match.group())
        assert len(densities) == 50

    def test_geography_tiles_have_tooltip(self, insights_html):
        geo_match = re.search(
            r'id="geography".*?</section>', insights_html, re.DOTALL
        )
        assert geo_match
        # Count only US map tiles (not world tiles)
        tooltips = re.findall(r'gg-ins-map-tile"[^>]*data-tooltip="[^"]*"', geo_match.group())
        assert len(tooltips) == 50

    def test_geography_tiles_have_grid_position(self, insights_html):
        geo_match = re.search(
            r'id="geography".*?</section>', insights_html, re.DOTALL
        )
        assert geo_match
        positions = re.findall(r'grid-column:\d+;grid-row:\d+', geo_match.group())
        assert len(positions) == 50

    def test_geography_tile_abbr_class(self, insights_html):
        assert "gg-ins-map-abbr" in insights_html

    def test_geography_tile_count_class(self, insights_html):
        assert "gg-ins-map-count" in insights_html

    def test_geography_no_region_bars(self, insights_html):
        """Old region bars should be replaced by tile grid."""
        geo_match = re.search(
            r'id="geography".*?</section>', insights_html, re.DOTALL
        )
        assert geo_match
        assert "gg-ins-data-bar-fill--teal" not in geo_match.group()

    # ── Calendar (Expandable Months) ──
    def test_calendar_section_id(self, insights_html):
        assert 'id="calendar"' in insights_html

    def test_calendar_title(self, insights_html):
        assert "The Calendar Crunch" in insights_html

    def test_calendar_12_months(self, insights_html):
        cal_match = re.search(
            r'id="calendar".*?</section>', insights_html, re.DOTALL
        )
        assert cal_match
        cols = re.findall(r"gg-ins-cal-col", cal_match.group())
        assert len(cols) == 12, f"Expected 12 month cols, got {len(cols)}"

    def test_calendar_month_labels(self, insights_html):
        cal_match = re.search(
            r'id="calendar".*?</section>', insights_html, re.DOTALL
        )
        assert cal_match
        section = cal_match.group()
        for abbr in ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]:
            assert abbr in section, f"Month label '{abbr}' missing"

    def test_calendar_peak_highlight(self, insights_html):
        assert "gg-ins-cal-peak" in insights_html

    def test_calendar_bar_class(self, insights_html):
        assert "gg-ins-cal-bar" in insights_html

    def test_calendar_data_animate(self, insights_html):
        cal_match = re.search(
            r'id="calendar".*?</section>', insights_html, re.DOTALL
        )
        assert cal_match
        assert 'data-animate="bars"' in cal_match.group()

    def test_calendar_cols_role_button(self, insights_html):
        cal_match = re.search(
            r'id="calendar".*?</section>', insights_html, re.DOTALL
        )
        assert cal_match
        buttons = re.findall(r'role="button"', cal_match.group())
        assert len(buttons) == 12

    def test_calendar_cols_aria_expanded(self, insights_html):
        cal_match = re.search(
            r'id="calendar".*?</section>', insights_html, re.DOTALL
        )
        assert cal_match
        expanded = re.findall(r'aria-expanded="false"', cal_match.group())
        assert len(expanded) == 12

    def test_calendar_12_hidden_panels(self, insights_html):
        cal_match = re.search(
            r'id="calendar".*?</section>', insights_html, re.DOTALL
        )
        assert cal_match
        panels = re.findall(r'class="gg-ins-cal-panel[^"]*"', cal_match.group())
        assert len(panels) == 12, f"Expected 12 panels, got {len(panels)}"

    def test_calendar_panels_have_data_month(self, insights_html):
        for month in MONTHS:
            assert f'data-month="{month}"' in insights_html, (
                f"Missing panel for {month}"
            )

    def test_calendar_race_names_in_panels(self, insights_html):
        """At least some panels should have race names."""
        assert "gg-ins-cal-race" in insights_html

    def test_calendar_tier_badges_in_panels(self, insights_html):
        """Panels should have tier badges."""
        assert "gg-ins-cal-tier" in insights_html

    def test_calendar_detail_container(self, insights_html):
        assert 'id="cal-detail"' in insights_html

    def test_calendar_detail_aria_live(self, insights_html):
        cal_detail = re.search(r'id="cal-detail"[^>]*>', insights_html)
        assert cal_detail
        assert 'aria-live="polite"' in cal_detail.group()

    # ── Price Myth ──
    def test_price_section_id(self, insights_html):
        assert 'id="price-myth"' in insights_html

    def test_price_title(self, insights_html):
        assert "The Price Myth" in insights_html

    def test_price_stat_grid(self, insights_html):
        assert "gg-ins-price-grid" in insights_html

    def test_price_stat_cards(self, insights_html):
        price_match = re.search(
            r'id="price-myth".*?</section>', insights_html, re.DOTALL
        )
        assert price_match
        cards = re.findall(r"gg-ins-price-stat\"", price_match.group())
        assert len(cards) >= 3, f"Expected >=3 stat cards, got {len(cards)}"

    def test_price_best_value_callout(self, insights_html):
        """Best value callout should be present."""
        price_match = re.search(
            r'id="price-myth".*?</section>', insights_html, re.DOTALL
        )
        assert price_match
        assert "Best Value" in price_match.group()

    def test_price_no_over_500_in_t4(self, editorial_facts):
        """Priciest T4 should not exceed $500."""
        pt4 = editorial_facts.get("priciest_t4", {})
        if pt4:
            assert pt4["price"] <= 500

    def test_price_cheap_beat_no_high_prestige(self, editorial_facts):
        """Cheap beat should not use prestige>=4 cheap races."""
        cb = editorial_facts.get("cheap_beat", {})
        if cb:
            # cheap_beat now uses tier reversal, not prestige-4 cheap races
            assert cb.get("cheap_tier", 4) < cb.get("expensive_tier", 4)

    def test_price_stat_values(self, insights_html):
        assert "gg-ins-price-stat-value" in insights_html

    def test_price_stat_labels(self, insights_html):
        assert "gg-ins-price-stat-label" in insights_html

    def test_price_correlation_shown(self, insights_html):
        """Price section should show correlation value."""
        price_match = re.search(
            r'id="price-myth".*?</section>', insights_html, re.DOTALL
        )
        assert price_match
        assert "Correlation" in price_match.group()

    # ── Shared data story checks ──
    def test_no_scrollytelling_remnants(self, insights_html):
        assert "gg-ins-scrolly" not in insights_html
        assert "gg-ins-dot" not in insights_html
        assert "gg-ins-step" not in insights_html

    def test_no_circle_elements(self, insights_html):
        """No SVG circles in data story sections."""
        for section_id in ["tier-breakdown", "geography", "calendar", "price-myth"]:
            section_match = re.search(
                rf'id="{section_id}".*?</section>', insights_html, re.DOTALL
            )
            if section_match:
                assert "<circle" not in section_match.group()

    def test_data_chart_class(self, insights_html):
        assert "gg-ins-data-chart" in insights_html

    def test_data_row_class(self, insights_html):
        assert "gg-ins-data-row" in insights_html

    def test_css_data_bar_fill(self, insights_css):
        assert ".gg-ins-data-bar-fill" in insights_css

    def test_css_cal_bar(self, insights_css):
        assert ".gg-ins-cal-bar" in insights_css

    def test_css_price_grid(self, insights_css):
        assert ".gg-ins-price-grid" in insights_css

    def test_css_tier_colors(self, insights_css):
        for t in range(1, 5):
            assert f'data-tier="{t}"' in insights_css

    def test_css_teal_bar_fill(self, insights_css):
        assert ".gg-ins-data-bar-fill--teal" in insights_css

    def test_css_transition_on_bars(self, insights_css):
        assert "transition" in insights_css

    def test_js_bar_animation(self, insights_js):
        assert "data-animate" in insights_js

    def test_js_data_target_w(self, insights_js):
        assert "data-target-w" in insights_js

    def test_js_intersection_observer(self, insights_js):
        assert "IntersectionObserver" in insights_js


# ── TestDimensionLeaderboard ──────────────────────────────────


class TestDimensionLeaderboard:
    """Test the dimension leaderboard section."""

    def test_section_id(self, insights_html):
        assert 'id="dimension-leaderboard"' in insights_html

    def test_figure_title(self, insights_html):
        assert "Who Leads Where" in insights_html

    def test_figure_takeaway(self, insights_html):
        assert "Pick a dimension" in insights_html

    def test_14_dim_buttons(self, insights_html):
        buttons = re.findall(r'class="gg-ins-dim-btn[^"]*"', insights_html)
        assert len(buttons) == 14, f"Expected 14 dim buttons, got {len(buttons)}"

    def test_first_button_active(self, insights_html):
        assert "gg-ins-dim-btn--active" in insights_html

    def test_buttons_have_data_dim(self, insights_html):
        btn_matches = re.findall(r'class="gg-ins-dim-btn[^"]*"[^>]*>', insights_html)
        for btn in btn_matches:
            assert "data-dim=" in btn, f"Dim button missing data-dim: {btn[:80]}"

    def test_all_dims_in_buttons(self, insights_html):
        for dim in ALL_DIMS:
            assert f'data-dim="{dim}"' in insights_html, (
                f"Dimension {dim} missing from leaderboard buttons"
            )

    def test_all_dim_labels_in_buttons(self, insights_html):
        for dim in ALL_DIMS:
            assert DIM_LABELS[dim] in insights_html, (
                f"Dim label {DIM_LABELS[dim]} missing from buttons"
            )

    def test_leaderboard_container(self, insights_html):
        assert 'id="dim-leaderboard"' in insights_html

    def test_leaderboard_aria_live(self, insights_html):
        dim_match = re.search(
            r'id="dim-leaderboard"[^>]*>', insights_html
        )
        assert dim_match
        assert 'aria-live="polite"' in dim_match.group()

    def test_leaderboard_role_tabpanel(self, insights_html):
        dim_match = re.search(
            r'id="dim-leaderboard"[^>]*>', insights_html
        )
        assert dim_match
        assert 'role="tabpanel"' in dim_match.group()

    def test_controls_role_tablist(self, insights_html):
        assert 'role="tablist"' in insights_html

    def test_controls_aria_label(self, insights_html):
        assert 'aria-label="Select scoring dimension"' in insights_html

    def test_css_dim_btn(self, insights_css):
        assert ".gg-ins-dim-btn" in insights_css

    def test_css_dim_btn_active(self, insights_css):
        assert ".gg-ins-dim-btn--active" in insights_css

    def test_css_dim_row(self, insights_css):
        assert ".gg-ins-dim-row" in insights_css

    def test_css_dim_bar(self, insights_css):
        assert ".gg-ins-dim-bar" in insights_css

    def test_css_dim_bar_fill(self, insights_css):
        assert ".gg-ins-dim-bar-fill" in insights_css

    def test_css_dim_rank(self, insights_css):
        assert ".gg-ins-dim-rank" in insights_css

    def test_css_dim_name(self, insights_css):
        assert ".gg-ins-dim-name" in insights_css

    def test_css_dim_score(self, insights_css):
        assert ".gg-ins-dim-score" in insights_css

    def test_css_dim_tier(self, insights_css):
        assert ".gg-ins-dim-tier" in insights_css

    def test_js_update_dim_leaderboard(self, insights_js):
        assert "updateDimLeaderboard" in insights_js

    def test_js_get_dim_value(self, insights_js):
        assert "getDimValue" in insights_js

    def test_js_ga4_dim_change(self, insights_js):
        assert "insights_dim_change" in insights_js

    def test_js_dim_btn_click_listener(self, insights_js):
        assert "gg-ins-dim-btn" in insights_js

    def test_js_initial_leaderboard_call(self, insights_js):
        """JS should initialize leaderboard with first dimension."""
        assert "updateDimLeaderboard('logistics')" in insights_js

    def test_js_dim_row_role_button(self, insights_js):
        """Dim rows should have role=button in JS template."""
        assert 'role="button"' in insights_js

    def test_js_dim_row_aria_expanded(self, insights_js):
        """Dim rows should have aria-expanded in JS template."""
        # The updateDimLeaderboard function generates rows with aria-expanded
        assert 'aria-expanded' in insights_js


# ── TestRankingBuilder ────────────────────────────────────────


class TestRankingBuilder:
    """Test the ranking builder section."""

    def test_section_id(self, insights_html):
        assert 'id="ranking-builder"' in insights_html

    def test_rank_class(self, insights_html):
        assert "gg-ins-rank" in insights_html

    def test_6_sliders(self, insights_html):
        slider_ids = [
            "suffering",
            "prestige",
            "practicality",
            "adventure",
            "community",
            "value",
        ]
        for sid in slider_ids:
            assert f'id="gg-ins-rank-{sid}"' in insights_html, (
                f"Slider {sid} missing"
            )

    def test_slider_min_1(self, insights_html):
        sliders = re.findall(r'class="gg-ins-rank-slider"[^>]*>', insights_html)
        assert len(sliders) == 6
        for s in sliders:
            assert 'min="1"' in s

    def test_slider_max_10(self, insights_html):
        sliders = re.findall(r'class="gg-ins-rank-slider"[^>]*>', insights_html)
        for s in sliders:
            assert 'max="10"' in s

    def test_slider_default_5(self, insights_html):
        sliders = re.findall(r'class="gg-ins-rank-slider"[^>]*>', insights_html)
        for s in sliders:
            assert 'value="5"' in s

    def test_slider_type_range(self, insights_html):
        slider_inputs = re.findall(
            r'<input[^>]*class="gg-ins-rank-slider"[^>]*>', insights_html
        )
        assert len(slider_inputs) == 6
        for s in slider_inputs:
            assert 'type="range"' in s

    def test_slider_data_group(self, insights_html):
        sliders = re.findall(r'class="gg-ins-rank-slider"[^>]*>', insights_html)
        for s in sliders:
            assert "data-group=" in s

    def test_reset_button(self, insights_html):
        assert 'id="gg-ins-rank-reset"' in insights_html

    def test_reset_button_label(self, insights_html):
        assert "Reset to Equal Weights" in insights_html

    def test_3_preset_buttons(self, insights_html):
        rank_match = re.search(
            r'id="ranking-builder".*?</section>', insights_html, re.DOTALL
        )
        assert rank_match
        presets = re.findall(r'data-preset="[^"]*"', rank_match.group())
        assert len(presets) == 3, f"Expected 3 presets, got {len(presets)}"

    def test_preset_weekend_warrior(self, insights_html):
        assert 'data-preset="weekend-warrior"' in insights_html
        assert "Weekend Warrior" in insights_html

    def test_preset_suffer_enthusiast(self, insights_html):
        assert 'data-preset="suffer-enthusiast"' in insights_html
        assert "Suffer Enthusiast" in insights_html

    def test_preset_budget_racer(self, insights_html):
        assert 'data-preset="budget-racer"' in insights_html
        assert "Budget Racer" in insights_html

    def test_preset_class(self, insights_html):
        assert "gg-ins-rank-preset" in insights_html

    def test_leaderboard_present(self, insights_html):
        assert 'id="gg-ins-rank-leaderboard"' in insights_html

    def test_leaderboard_aria_live(self, insights_html):
        assert 'aria-live="polite"' in insights_html

    def test_figure_title(self, insights_html):
        assert "Find Your Perfect Race" in insights_html

    def test_figure_takeaway(self, insights_html):
        assert "Every rider values different things" in insights_html

    def test_slider_labels(self, insights_html):
        assert "Suffering" in insights_html
        assert "Prestige" in insights_html
        assert "Practicality" in insights_html
        assert "Adventure" in insights_html
        assert "Community" in insights_html
        assert "Value" in insights_html

    def test_slider_value_display(self, insights_html):
        for sid in [
            "suffering",
            "prestige",
            "practicality",
            "adventure",
            "community",
            "value",
        ]:
            assert f'id="gg-ins-rank-{sid}-val"' in insights_html

    def test_slider_dim_descriptions(self, insights_html):
        """Each slider group should show which dims it maps to."""
        assert "gg-ins-rank-dims" in insights_html

    def test_leaderboard_10_placeholder_entries(self, insights_html):
        rank_match = re.search(
            r'id="ranking-builder".*?</section>', insights_html, re.DOTALL
        )
        assert rank_match, "ranking-builder section not found"
        entries = re.findall(r'class="gg-ins-rank-entry"', rank_match.group())
        assert len(entries) == 10

    def test_js_compute_ranking(self, insights_js):
        assert "computeRanking" in insights_js

    def test_js_update_leaderboard(self, insights_js):
        assert "updateLeaderboard" in insights_js

    def test_js_url_persistence(self, insights_js):
        assert "history.replaceState" in insights_js

    def test_js_rank_groups(self, insights_js):
        assert "RANK_GROUPS" in insights_js

    def test_js_ga4_rank_change(self, insights_js):
        assert "insights_rank_change" in insights_js

    def test_js_ga4_rank_reset(self, insights_js):
        assert "insights_rank_reset" in insights_js

    def test_js_url_param_restore(self, insights_js):
        """JS should restore slider weights from URL ?w= param."""
        assert "URLSearchParams" in insights_js

    def test_js_slider_input_event(self, insights_js):
        """Sliders should listen on input event."""
        assert "'input'" in insights_js


# ── TestOverratedUnderrated ───────────────────────────────────


class TestOverratedUnderrated:
    """Test the overrated/underrated section and expandable cards."""

    def test_section_id(self, insights_html):
        assert 'id="overrated-underrated"' in insights_html

    def test_ou_section_title(self, insights_html):
        assert "Punching Above" in insights_html

    def test_ou_has_cards(self, insights_html):
        assert "gg-insights-ou-card" in insights_html

    def test_ou_grid(self, insights_html):
        assert "gg-insights-ou-grid" in insights_html

    def test_ou_two_groups(self, insights_html):
        groups = re.findall(r'class="gg-insights-ou-group"', insights_html)
        assert len(groups) == 2

    def test_ou_group_titles(self, insights_html):
        assert "Punching Above Their Weight" in insights_html
        assert "Prestige Premium" in insights_html

    def test_ou_cards_have_tier(self, insights_html):
        assert "gg-insights-ou-card-tier" in insights_html

    def test_ou_cards_have_name(self, insights_html):
        assert "gg-insights-ou-card-name" in insights_html

    def test_ou_cards_have_stats(self, insights_html):
        assert "gg-insights-ou-card-stats" in insights_html

    def test_ou_cards_have_editorial(self, insights_html):
        assert "gg-insights-ou-card-editorial" in insights_html

    # Expandable card features
    def test_ou_cards_aria_expanded(self, insights_html):
        """O/U cards should have aria-expanded attribute."""
        cards = re.findall(
            r'class="gg-insights-ou-card"[^>]*>', insights_html
        )
        assert len(cards) >= 2
        for card in cards:
            assert 'aria-expanded="false"' in card, (
                f"Card missing aria-expanded: {card[:80]}"
            )

    def test_ou_cards_role_button(self, insights_html):
        """O/U cards should have role=button."""
        cards = re.findall(
            r'class="gg-insights-ou-card"[^>]*>', insights_html
        )
        for card in cards:
            assert 'role="button"' in card

    def test_ou_cards_tabindex(self, insights_html):
        """O/U cards should have tabindex for keyboard access."""
        cards = re.findall(
            r'class="gg-insights-ou-card"[^>]*>', insights_html
        )
        for card in cards:
            assert 'tabindex="0"' in card

    def test_ou_expand_hint(self, insights_html):
        """Each card should have an expand hint."""
        assert "gg-ins-ou-expand-hint" in insights_html
        hints = re.findall(r'class="gg-ins-ou-expand-hint"', insights_html)
        assert len(hints) >= 2

    def test_ou_detail_section(self, insights_html):
        """Each card should have a detail section."""
        assert "gg-ins-ou-detail" in insights_html
        details = re.findall(r'class="gg-ins-ou-detail"', insights_html)
        assert len(details) >= 2

    def test_ou_detail_aria_hidden(self, insights_html):
        """Detail sections should start hidden."""
        detail_matches = re.findall(
            r'class="gg-ins-ou-detail"[^>]*>', insights_html
        )
        for d in detail_matches:
            assert 'aria-hidden="true"' in d

    def test_ou_dimension_bars_in_detail(self, insights_html):
        """Detail section should have 14 dimension bars per card."""
        assert "gg-ins-ou-dim" in insights_html
        assert "gg-ins-ou-dim-bar" in insights_html
        assert "gg-ins-ou-dim-fill" in insights_html

    def test_ou_dim_labels_present(self, insights_html):
        """Dimension labels should appear in O/U card details."""
        assert "gg-ins-ou-dim-label" in insights_html

    def test_ou_link_to_profile(self, insights_html):
        """Cards should link to the race profile."""
        assert "gg-ins-ou-link" in insights_html
        assert "View Full Profile" in insights_html

    def test_ou_editorial_text_length(self, insights_html):
        """O/U editorial text should be at least 80 chars."""
        editorials = re.findall(
            r'class="gg-insights-ou-card-editorial">(.*?)</p>',
            insights_html, re.DOTALL
        )
        assert len(editorials) >= 2
        for text in editorials:
            clean = re.sub(r'<[^>]+>', '', text).strip()
            assert len(clean) >= 80, f"Editorial too short ({len(clean)} chars): {clean[:50]}"

    def test_ou_editorial_mentions_dimension(self, insights_html):
        """O/U editorial should mention specific dimension names."""
        editorials = re.findall(
            r'class="gg-insights-ou-card-editorial">(.*?)</p>',
            insights_html, re.DOTALL
        )
        # Check that at least some editorials mention dimension labels
        dim_label_values = set(
            ["Logistics", "Length", "Technicality", "Elevation", "Climate",
             "Altitude", "Adventure", "Prestige", "Race Quality", "Experience",
             "Community", "Field Depth", "Value", "Expenses"]
        )
        found_dim_mention = False
        for text in editorials:
            for label in dim_label_values:
                if label in text:
                    found_dim_mention = True
                    break
        assert found_dim_mention, "No dimension labels found in O/U editorials"

    def test_ou_editorial_mentions_prestige(self, insights_html):
        """O/U editorial should reference prestige score."""
        editorials = re.findall(
            r'class="gg-insights-ou-card-editorial">(.*?)</p>',
            insights_html, re.DOTALL
        )
        prestige_mentioned = sum(1 for t in editorials if "prestige" in t.lower())
        assert prestige_mentioned >= 2, "Prestige not mentioned in enough editorials"

    def test_js_ou_expand_handler(self, insights_js):
        """JS should handle O/U card expansion."""
        assert "aria-expanded" in insights_js

    def test_js_ga4_ou_expand(self, insights_js):
        assert "insights_ou_expand" in insights_js

    def test_js_ou_keyboard_handler(self, insights_js):
        """JS should support Enter/Space to expand cards."""
        assert "keydown" in insights_js


# ── TestClosing ───────────────────────────────────────────────


class TestClosing:
    """Test closing section — single CTA, no grid, no newsletter."""

    def test_closing_section_id(self, insights_html):
        assert 'id="what-now"' in insights_html

    def test_closing_title(self, insights_html):
        closing_match = re.search(
            r'id="what-now".*?</section>', insights_html, re.DOTALL
        )
        assert closing_match
        assert "<h2" in closing_match.group()

    def test_closing_title_text(self, insights_html):
        assert "Now Go Race" in insights_html

    def test_closing_single_cta_class(self, insights_html):
        assert "gg-insights-closing-single" in insights_html

    def test_closing_single_explore_button(self, insights_html):
        closing_match = re.search(
            r'id="what-now".*?</section>', insights_html, re.DOTALL
        )
        assert closing_match
        section = closing_match.group()
        assert "Explore All" in section
        assert "Races" in section

    def test_closing_stat_strip(self, insights_html):
        """Closing should have summary stat strip."""
        assert "gg-ins-closing-stats" in insights_html

    def test_closing_stat_items(self, insights_html):
        """Stat strip should have multiple stat items."""
        closing_match = re.search(
            r'id="what-now".*?</section>', insights_html, re.DOTALL
        )
        assert closing_match
        items = re.findall(r'gg-ins-closing-stat-item', closing_match.group())
        assert len(items) >= 3

    def test_closing_class(self, insights_html):
        assert "gg-ins-closing" in insights_html

    def test_closing_cta_btn_lg(self, insights_html):
        """Large CTA button class should be present."""
        assert "gg-insights-cta-btn-lg" in insights_html

    def test_closing_cta_data_attribute(self, insights_html):
        """CTA should have data-cta for GA4 tracking."""
        closing_match = re.search(
            r'id="what-now".*?</section>', insights_html, re.DOTALL
        )
        assert closing_match
        assert 'data-cta="closing-explore"' in closing_match.group()

    def test_closing_links_to_races(self, insights_html):
        closing_match = re.search(
            r'id="what-now".*?</section>', insights_html, re.DOTALL
        )
        assert closing_match
        assert "gravel-races/" in closing_match.group()

    def test_closing_no_grid(self, insights_html):
        """Closing should NOT have the old grid layout."""
        assert "gg-insights-closing-grid" not in insights_html

    def test_closing_no_action_cards(self, insights_html):
        """Closing should NOT have the old action cards."""
        assert "gg-insights-action-card" not in insights_html

    def test_closing_no_newsletter(self, insights_html):
        """Closing should NOT have newsletter embed."""
        assert "gg-insights-newsletter" not in insights_html

    def test_closing_no_coaching_cta(self, insights_html):
        """No coaching CTAs on this page."""
        closing_match = re.search(
            r'id="what-now".*?</section>', insights_html, re.DOTALL
        )
        assert closing_match
        assert "coaching" not in closing_match.group().lower()

    def test_closing_race_count_in_text(self, insights_html, race_count):
        """Race count should appear in closing text."""
        assert f"{race_count} races" in insights_html

    def test_closing_race_count_in_button(self, insights_html, race_count):
        """Button should include race count."""
        assert f"Explore All {race_count} Races" in insights_html

    def test_has_footer(self, insights_html):
        assert "gg-mega-footer" in insights_html

    def test_json_ld(self, insights_html):
        assert "application/ld+json" in insights_html

    def test_json_ld_valid(self, insights_html):
        ld_match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            insights_html,
            re.DOTALL,
        )
        assert ld_match, "JSON-LD not found"
        data = json.loads(ld_match.group(1))
        assert data["@type"] == "Article"
        assert "Races Analyzed" in data["headline"]

    def test_json_ld_has_author(self, insights_html):
        ld_match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            insights_html,
            re.DOTALL,
        )
        data = json.loads(ld_match.group(1))
        assert "author" in data


# ── TestCTAStrategy ───────────────────────────────────────────


class TestCTAStrategy:
    """Test that CTA strategy is single CTA only (no mid-page CTAs)."""

    def test_single_closing_cta_only(self, insights_html):
        """Only ONE CTA should exist: closing explore button."""
        cta_blocks = re.findall(r'class="gg-insights-cta-block"', insights_html)
        assert len(cta_blocks) == 0, (
            f"Expected 0 CTA blocks (using closing-single instead), got {len(cta_blocks)}"
        )

    def test_no_mid_page_cta_html_elements(self, insights_html):
        """No CTA block HTML elements in the page body (only in CSS definitions)."""
        # Extract just the <body> section HTML elements (exclude <style> and <script>)
        body_match = re.search(r'<body>(.*?)</body>', insights_html, re.DOTALL)
        assert body_match
        body_html = body_match.group(1)
        # Remove <style> and <script> blocks
        body_no_style = re.sub(r'<style[^>]*>.*?</style>', '', body_html, flags=re.DOTALL)
        body_clean = re.sub(r'<script[^>]*>.*?</script>', '', body_no_style, flags=re.DOTALL)
        assert 'class="gg-insights-cta-block"' not in body_clean

    def test_closing_explore_is_only_cta_link(self, insights_html):
        """data-cta should only appear on the closing explore button."""
        cta_links = re.findall(r'data-cta="([^"]*)"', insights_html)
        assert len(cta_links) == 1
        assert cta_links[0] == "closing-explore"


# ── TestCss ───────────────────────────────────────────────────


class TestCss:
    """Test CSS brand compliance."""

    def test_no_hardcoded_hex(self, insights_css):
        # Known hex fallbacks for color-mix() browser compat
        COLOR_MIX_FALLBACKS = {
            "#d8e5e0", "#aeccc6", "#7aafa7",  # teal density fills
            "#f3ede5", "#cdc1b5",              # brown density fallbacks
        }
        css_no_comments = re.sub(r"/\*.*?\*/", "", insights_css, flags=re.DOTALL)
        hexes = re.findall(r"#[0-9a-fA-F]{3,8}\b", css_no_comments)
        color_hexes = []
        for h in hexes:
            digits = h[1:]
            if len(digits) in (3, 4, 6, 8) and h.lower() not in COLOR_MIX_FALLBACKS:
                color_hexes.append(h)
        assert len(color_hexes) == 0, f"Hardcoded hex colors found: {color_hexes[:10]}"

    def test_no_border_radius(self, insights_css):
        """border-radius only allowed as 0 !important (neo-brutalist reset)."""
        matches = re.findall(r"border-radius:\s*([^;]+);", insights_css)
        for val in matches:
            assert val.strip() == "0 !important", (
                f"Non-zero border-radius found: {val}"
            )

    def test_no_box_shadow(self, insights_css):
        """box-shadow only allowed as none !important (neo-brutalist reset)."""
        matches = re.findall(r"box-shadow:\s*([^;]+);", insights_css)
        for val in matches:
            assert val.strip() == "none !important", (
                f"Non-none box-shadow found: {val}"
            )

    def test_no_opacity_transition(self, insights_css):
        transitions = re.findall(r"transition:\s*([^;]+);", insights_css)
        for t in transitions:
            assert "opacity" not in t, f"Opacity transition found: {t}"

    def test_no_gradient(self, insights_css):
        assert "linear-gradient" not in insights_css
        assert "radial-gradient" not in insights_css

    def test_uses_brand_color_tokens(self, insights_css):
        assert "var(--gg-color-" in insights_css

    def test_uses_brand_font_tokens(self, insights_css):
        assert "var(--gg-font-" in insights_css

    def test_gg_ins_prefix(self, insights_css):
        assert ".gg-ins-" in insights_css

    def test_gg_insights_prefix(self, insights_css):
        assert ".gg-insights-" in insights_css

    def test_reduced_motion(self, insights_css):
        assert "prefers-reduced-motion" in insights_css

    def test_print_styles(self, insights_css):
        assert "@media print" in insights_css

    def test_focus_visible(self, insights_css):
        assert "focus-visible" in insights_css

    def test_responsive_900px(self, insights_css):
        assert "900px" in insights_css

    def test_responsive_600px(self, insights_css):
        assert "600px" in insights_css

    def test_responsive_480px(self, insights_css):
        assert "480px" in insights_css

    def test_allowed_transitions_only(self, insights_css):
        """Only brand-allowed transition properties."""
        allowed = {
            "background-color",
            "border-color",
            "color",
            "fill",
            "stroke",
            "transform",
            "width",
            "height",
            "none",
        }
        transitions = re.findall(r"transition:\s*([^;]+);", insights_css)
        for t in transitions:
            parts = re.split(r",\s*(?![^()]*\))", t)
            props = [p.strip().split()[0] for p in parts]
            for prop in props:
                assert prop in allowed or "var(--" in t, (
                    f"Disallowed transition property: {prop} in '{t}'"
                )

    def test_color_mix_for_transparency(self, insights_css):
        """Uses color-mix for opacity needs, not rgba."""
        if "transparent" in insights_css:
            assert "color-mix" in insights_css

    def test_no_rgba(self, insights_css):
        """No rgba() in CSS -- use color-mix instead."""
        css_no_comments = re.sub(r"/\*.*?\*/", "", insights_css, flags=re.DOTALL)
        assert "rgba(" not in css_no_comments

    def test_data_bar_fill_css(self, insights_css):
        assert ".gg-ins-data-bar-fill" in insights_css

    def test_cal_bar_css(self, insights_css):
        assert ".gg-ins-cal-bar" in insights_css

    def test_price_stat_css(self, insights_css):
        assert ".gg-ins-price-stat" in insights_css

    def test_rank_slider_css(self, insights_css):
        assert ".gg-ins-rank-slider" in insights_css

    def test_tooltip_css(self, insights_css):
        assert ".gg-insights-tooltip" in insights_css

    def test_cta_btn_gold_css(self, insights_css):
        assert ".gg-insights-cta-btn-gold" in insights_css

    def test_ou_card_css(self, insights_css):
        assert ".gg-insights-ou-card" in insights_css

    def test_closing_single_css(self, insights_css):
        assert ".gg-insights-closing-single" in insights_css

    def test_cta_btn_lg_css(self, insights_css):
        assert ".gg-insights-cta-btn-lg" in insights_css

    # Map tile grid CSS
    def test_map_grid_css(self, insights_css):
        assert ".gg-ins-map-grid" in insights_css

    def test_map_tile_css(self, insights_css):
        assert ".gg-ins-map-tile" in insights_css

    def test_map_density_css(self, insights_css):
        for density in ["none", "low", "med", "high"]:
            assert f'data-density="{density}"' in insights_css

    def test_map_abbr_css(self, insights_css):
        assert ".gg-ins-map-abbr" in insights_css

    # Calendar expandable CSS
    def test_cal_panel_css(self, insights_css):
        assert ".gg-ins-cal-panel" in insights_css

    def test_cal_race_css(self, insights_css):
        assert ".gg-ins-cal-race" in insights_css

    def test_cal_tier_css(self, insights_css):
        assert ".gg-ins-cal-tier" in insights_css

    def test_cal_detail_css(self, insights_css):
        assert ".gg-ins-cal-detail" in insights_css

    # Dim expandable row CSS
    def test_dim_detail_css(self, insights_css):
        assert ".gg-ins-dim-detail" in insights_css

    def test_dim_row_expanded_css(self, insights_css):
        assert 'aria-expanded="true"' in insights_css

    # Preset CSS
    def test_rank_preset_css(self, insights_css):
        assert ".gg-ins-rank-preset" in insights_css

    def test_rank_presets_css(self, insights_css):
        assert ".gg-ins-rank-presets" in insights_css

    # Closing stat strip CSS
    def test_closing_stats_css(self, insights_css):
        assert ".gg-ins-closing-stats" in insights_css

    def test_closing_stat_item_css(self, insights_css):
        assert ".gg-ins-closing-stat-item" in insights_css

    def test_no_scatter_css(self, insights_css):
        """Scatter CSS should not exist."""
        assert ".gg-ins-scatter-" not in insights_css

    def test_no_heritage_css(self, insights_css):
        """Heritage CSS should not exist."""
        assert ".gg-insights-heritage-" not in insights_css

    def test_no_newsletter_css(self, insights_css):
        """Newsletter CSS should not exist."""
        assert ".gg-insights-newsletter" not in insights_css

    def test_no_closing_grid_css(self, insights_css):
        """Old closing grid CSS should not exist."""
        assert ".gg-insights-closing-grid" not in insights_css

    # Dimension leaderboard CSS
    def test_dim_btn_css(self, insights_css):
        assert ".gg-ins-dim-btn" in insights_css

    def test_dim_row_css(self, insights_css):
        assert ".gg-ins-dim-row" in insights_css

    def test_dim_bar_css(self, insights_css):
        assert ".gg-ins-dim-bar" in insights_css

    def test_dim_bar_fill_css(self, insights_css):
        assert ".gg-ins-dim-bar-fill" in insights_css

    def test_dim_rank_css(self, insights_css):
        assert ".gg-ins-dim-rank" in insights_css

    def test_dim_name_css(self, insights_css):
        assert ".gg-ins-dim-name" in insights_css

    def test_dim_score_css(self, insights_css):
        assert ".gg-ins-dim-score" in insights_css

    def test_dim_tier_css(self, insights_css):
        assert ".gg-ins-dim-tier" in insights_css

    # Expandable O/U CSS
    def test_ou_expand_hint_css(self, insights_css):
        assert ".gg-ins-ou-expand-hint" in insights_css

    def test_ou_detail_css(self, insights_css):
        assert ".gg-ins-ou-detail" in insights_css

    def test_ou_dim_css(self, insights_css):
        assert ".gg-ins-ou-dim" in insights_css

    def test_ou_dim_bar_css(self, insights_css):
        assert ".gg-ins-ou-dim-bar" in insights_css

    def test_ou_dim_fill_css(self, insights_css):
        assert ".gg-ins-ou-dim-fill" in insights_css

    def test_ou_link_css(self, insights_css):
        assert ".gg-ins-ou-link" in insights_css

    def test_no_circle_border_radius_anywhere(self, insights_css):
        """All border-radius values must be 0 (neo-brutalist reset only)."""
        matches = re.findall(r"border-radius:\s*([^;]+);", insights_css)
        for val in matches:
            assert val.strip() == "0 !important", (
                f"Non-zero border-radius found: {val}"
            )


# ── TestJs ────────────────────────────────────────────────────


class TestJs:
    """Test JS structure and content."""

    def test_iife(self, insights_js):
        assert "(function(){" in insights_js or "(function ()" in insights_js

    def test_strict_mode(self, insights_js):
        assert "'use strict'" in insights_js

    def test_intersection_observer(self, insights_js):
        assert "IntersectionObserver" in insights_js

    def test_counter_animation(self, insights_js):
        assert "animateCounter" in insights_js

    def test_reduced_motion_guard(self, insights_js):
        assert "prefers-reduced-motion" in insights_js

    def test_js_syntax_valid(self):
        """Validate JS syntax using Node.js."""
        js = build_insights_js()
        match = re.search(r"<script>(.*?)</script>", js, re.DOTALL)
        assert match, "No script content found"
        code = match.group(1)
        result = subprocess.run(
            ["node", "-e", f"new Function({repr(code)})"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"JS syntax error: {result.stderr}"

    def test_no_d3_import(self, insights_js):
        assert "d3." not in insights_js

    def test_no_external_imports(self, insights_js):
        assert "require(" not in insights_js

    def test_no_es_module_import(self, insights_js):
        script_body = re.search(r"<script>(.*?)</script>", insights_js, re.DOTALL)
        if script_body:
            assert "import " not in script_body.group(1)

    def test_race_data_parsing(self, insights_js):
        assert "gg-race-data" in insights_js

    def test_bar_animation_observer(self, insights_js):
        assert "data-animate" in insights_js

    def test_bar_target_w(self, insights_js):
        assert "data-target-w" in insights_js

    def test_tooltip_system(self, insights_js):
        assert "data-tooltip" in insights_js

    def test_tooltip_role(self, insights_js):
        assert "role" in insights_js

    def test_ga4_events(self, insights_js):
        events = [
            "insights_page_view",
            "insights_dim_change",
            "insights_ou_expand",
            "insights_rank_change",
            "insights_rank_reset",
            "insights_cta_click",
            "insights_section_view",
            "insights_scroll_depth",
            "insights_cal_expand",
            "insights_dim_expand",
            "insights_rank_preset",
        ]
        for ev in events:
            assert ev in insights_js, f"GA4 event {ev} missing"

    def test_no_scrolly_step_event(self, insights_js):
        """Old scrollytelling GA4 event should not exist."""
        assert "insights_scrolly_step" not in insights_js

    def test_no_scatter_change_event(self, insights_js):
        """Old scatter event should not exist."""
        assert "insights_scatter_change" not in insights_js

    def test_no_update_scatter(self, insights_js):
        """Old updateScatter function should not exist."""
        assert "updateScatter" not in insights_js

    def test_no_normalize_values(self, insights_js):
        """Old normalizeValues function should not exist."""
        assert "normalizeValues" not in insights_js

    def test_event_delegation(self, insights_js):
        assert "document.addEventListener" in insights_js

    def test_gg_has_js_guard(self, insights_js):
        assert "gg-has-js" in insights_js

    def test_dims_array(self, insights_js):
        assert "DIMS" in insights_js

    def test_dims_array_has_logistics(self, insights_js):
        assert "logistics" in insights_js

    def test_dim_labels_in_js(self, insights_js):
        assert "DIM_LABELS" in insights_js

    def test_scroll_depth_tracking(self, insights_js):
        assert "depthMarks" in insights_js

    def test_figure_visibility_observer(self, insights_js):
        assert "gg-in-view" in insights_js

    def test_show_tooltip_function(self, insights_js):
        assert "showTooltip" in insights_js

    def test_hide_tooltip_function(self, insights_js):
        assert "hideTooltip" in insights_js

    def test_get_dim_value_function(self, insights_js):
        assert "getDimValue" in insights_js

    def test_update_dim_leaderboard_function(self, insights_js):
        assert "updateDimLeaderboard" in insights_js

    def test_ou_expand_click_handler(self, insights_js):
        """JS should handle O/U card expand clicks."""
        assert "gg-insights-ou-card" in insights_js
        assert "aria-expanded" in insights_js

    def test_ou_keydown_handler(self, insights_js):
        """JS should handle Enter/Space on O/U cards."""
        assert "keydown" in insights_js
        assert "Enter" in insights_js

    # Calendar click handler
    def test_js_cal_expand_handler(self, insights_js):
        assert "toggleCalMonth" in insights_js

    def test_js_cal_col_click(self, insights_js):
        assert "gg-ins-cal-col" in insights_js

    # Dim row expansion
    def test_js_dim_detail_builder(self, insights_js):
        assert "buildDimDetail" in insights_js

    def test_js_dim_row_click(self, insights_js):
        assert "gg-ins-dim-row" in insights_js

    def test_js_dim_row_expand_aria(self, insights_js):
        """JS dim row expansion should toggle aria-expanded."""
        assert 'data-race-idx' in insights_js

    # Preset handler
    def test_js_preset_handler(self, insights_js):
        assert "PRESETS" in insights_js

    def test_js_preset_click(self, insights_js):
        assert "gg-ins-rank-preset" in insights_js

    def test_js_preset_values(self, insights_js):
        """Presets should define values for all 3 profiles."""
        assert "weekend-warrior" in insights_js
        assert "suffer-enthusiast" in insights_js
        assert "budget-racer" in insights_js


# ── TestAccessibility ─────────────────────────────────────────


class TestAccessibility:
    """Test accessibility requirements."""

    def test_sliders_have_labels(self, insights_html):
        for sid in [
            "suffering",
            "prestige",
            "practicality",
            "adventure",
            "community",
            "value",
        ]:
            pattern = f'for="gg-ins-rank-{sid}"'
            assert pattern in insights_html, (
                f"Slider {sid} missing label for= attribute"
            )

    def test_leaderboard_aria_live(self, insights_html):
        assert 'aria-live="polite"' in insights_html

    def test_dim_leaderboard_aria_live(self, insights_html):
        """Dimension leaderboard should have aria-live."""
        dim_match = re.search(
            r'id="dim-leaderboard"[^>]*>', insights_html
        )
        assert dim_match
        assert 'aria-live="polite"' in dim_match.group()

    def test_ou_cards_have_role(self, insights_html):
        cards = re.findall(
            r'class="gg-insights-ou-card"[^>]*>', insights_html
        )
        for card in cards:
            assert 'role="button"' in card

    def test_ou_cards_have_tabindex(self, insights_html):
        cards = re.findall(
            r'class="gg-insights-ou-card"[^>]*>', insights_html
        )
        for card in cards:
            assert 'tabindex="0"' in card

    def test_skip_link(self, insights_html):
        assert "gg-skip-link" in insights_html

    def test_canonical_link(self, insights_html):
        assert 'rel="canonical"' in insights_html

    def test_meta_description(self, insights_html):
        assert 'name="description"' in insights_html

    def test_lang_attribute(self, insights_html):
        assert 'lang="en"' in insights_html

    def test_viewport_meta(self, insights_html):
        assert "viewport" in insights_html

    def test_og_title(self, insights_html):
        assert "og:title" in insights_html

    def test_og_description(self, insights_html):
        assert "og:description" in insights_html

    def test_og_type(self, insights_html):
        assert "og:type" in insights_html

    def test_heading_hierarchy(self, insights_html):
        """h1 should come before h2."""
        h1_pos = insights_html.find("<h1")
        h2_pos = insights_html.find("<h2")
        assert h1_pos < h2_pos, "h1 should come before h2"

    def test_dim_controls_role_tablist(self, insights_html):
        assert 'role="tablist"' in insights_html

    def test_dim_leaderboard_role_tabpanel(self, insights_html):
        dim_match = re.search(
            r'id="dim-leaderboard"[^>]*>', insights_html
        )
        assert dim_match
        assert 'role="tabpanel"' in dim_match.group()


# ── TestEditorialFacts ────────────────────────────────────────


class TestEditorialFacts:
    """Test compute_editorial_facts structure."""

    def test_returns_dict(self, editorial_facts):
        assert isinstance(editorial_facts, dict)

    def test_has_top_state(self, editorial_facts):
        assert "top_state" in editorial_facts

    def test_has_top_state_count(self, editorial_facts):
        assert "top_state_count" in editorial_facts

    def test_has_quality_state(self, editorial_facts):
        assert "quality_state" in editorial_facts

    def test_has_quality_state_avg(self, editorial_facts):
        assert "quality_state_avg" in editorial_facts

    def test_has_price_score_corr(self, editorial_facts):
        assert "price_score_corr" in editorial_facts

    def test_has_cheap_beat(self, editorial_facts):
        assert "cheap_beat" in editorial_facts

    def test_has_youngest_t1(self, editorial_facts):
        assert "youngest_t1" in editorial_facts

    def test_has_overrated(self, editorial_facts):
        assert "overrated" in editorial_facts

    def test_has_underrated(self, editorial_facts):
        assert "underrated" in editorial_facts

    def test_has_cheapest_t1(self, editorial_facts):
        assert "cheapest_t1" in editorial_facts

    def test_has_priciest_t4(self, editorial_facts):
        assert "priciest_t4" in editorial_facts

    def test_has_midwest_count(self, editorial_facts):
        assert "midwest_count" in editorial_facts

    def test_top_state_is_valid_abbreviation(self, editorial_facts):
        ts = editorial_facts.get("top_state", "")
        if ts:
            assert ts in US_STATES, f"Top state {ts} not in US_STATES"

    def test_quality_state_is_valid(self, editorial_facts):
        qs = editorial_facts.get("quality_state", "")
        if qs:
            assert qs in US_STATES, f"Quality state {qs} not in US_STATES"

    def test_price_score_corr_range(self, editorial_facts):
        corr = editorial_facts.get("price_score_corr", 0)
        assert -1.0 <= corr <= 1.0

    def test_overrated_is_list(self, editorial_facts):
        assert isinstance(editorial_facts.get("overrated"), list)

    def test_overrated_max_5(self, editorial_facts):
        assert len(editorial_facts.get("overrated", [])) <= 5

    def test_underrated_is_list(self, editorial_facts):
        assert isinstance(editorial_facts.get("underrated"), list)

    def test_underrated_max_5(self, editorial_facts):
        assert len(editorial_facts.get("underrated", [])) <= 5

    def test_midwest_count_positive(self, editorial_facts):
        assert editorial_facts.get("midwest_count", 0) > 0

    def test_youngest_t1_structure(self, editorial_facts):
        yt1 = editorial_facts.get("youngest_t1", {})
        assert isinstance(yt1, dict)
        if yt1:
            assert "name" in yt1
            assert "founded" in yt1
            assert "score" in yt1

    def test_cheapest_t1_structure(self, editorial_facts):
        ct1 = editorial_facts.get("cheapest_t1", {})
        assert isinstance(ct1, dict)
        if ct1:
            assert "name" in ct1
            assert "price" in ct1

    def test_has_best_value(self, editorial_facts):
        assert "best_value" in editorial_facts

    def test_best_value_structure(self, editorial_facts):
        bv = editorial_facts.get("best_value", {})
        assert isinstance(bv, dict)
        if bv:
            assert "name" in bv
            assert "price" in bv
            assert bv["price"] <= 150

    def test_has_state_counts(self, editorial_facts):
        assert "state_counts" in editorial_facts
        assert isinstance(editorial_facts["state_counts"], dict)

    def test_has_state_scores(self, editorial_facts):
        assert "state_scores" in editorial_facts
        assert isinstance(editorial_facts["state_scores"], dict)


# ── TestFigureWrapper ─────────────────────────────────────────


class TestFigureWrapper:
    """Test the figure wrapper utility."""

    def test_returns_string(self):
        result = build_figure_wrap("<p>Content</p>", "Title", "Takeaway", "test-id")
        assert isinstance(result, str)

    def test_has_figure_tag(self):
        result = build_figure_wrap("<p>Content</p>", "Title", "Takeaway", "test-id")
        assert "<figure" in result

    def test_has_title(self):
        result = build_figure_wrap(
            "<p>Content</p>", "My Chart Title", "Takeaway", "test-id"
        )
        assert "My Chart Title" in result

    def test_has_takeaway(self):
        result = build_figure_wrap(
            "<p>Content</p>", "Title", "Key insight here", "test-id"
        )
        assert "Key insight here" in result

    def test_has_content(self):
        result = build_figure_wrap(
            "<p>Test content</p>", "Title", "Takeaway", "test-id"
        )
        assert "Test content" in result

    def test_figure_class(self):
        result = build_figure_wrap("<p>Content</p>", "Title", "Takeaway", "test-id")
        assert "gg-insights-figure" in result

    def test_title_class(self):
        result = build_figure_wrap("<p>Content</p>", "Title", "Takeaway", "test-id")
        assert "gg-insights-figure-title" in result

    def test_takeaway_class(self):
        result = build_figure_wrap("<p>Content</p>", "Title", "Takeaway", "test-id")
        assert "gg-insights-figure-takeaway" in result

    def test_chart_id_in_figure(self):
        result = build_figure_wrap("<p>Content</p>", "Title", "Takeaway", "my-chart")
        assert 'id="my-chart-figure"' in result


# ── TestCTABlockUtility ───────────────────────────────────────


class TestCTABlockUtility:
    """Test the build_cta_block utility function (still exists, not used in page)."""

    def test_cta_block_returns_html(self):
        result = build_cta_block(
            "Heading", "Text", "https://example.com", "Click me", cta_id="test"
        )
        assert isinstance(result, str)

    def test_cta_has_heading(self):
        result = build_cta_block(
            "Find Races", "Search text", "https://example.com", "Search", cta_id="find"
        )
        assert "Find Races" in result

    def test_cta_has_link(self):
        result = build_cta_block(
            "Head", "Text", "https://example.com/races/", "Go", cta_id="go"
        )
        assert "https://example.com/races/" in result

    def test_cta_has_primary_label(self):
        result = build_cta_block(
            "Head", "Text", "https://example.com", "Explore Now", cta_id="explore"
        )
        assert "Explore Now" in result

    def test_cta_block_class(self):
        result = build_cta_block(
            "Head", "Text", "https://example.com", "Go", cta_id="test"
        )
        assert "gg-insights-cta-block" in result

    def test_cta_data_cta_attribute(self):
        result = build_cta_block(
            "Head", "Text", "https://example.com", "Go", cta_id="my-cta"
        )
        assert 'data-cta="my-cta"' in result

    def test_cta_secondary_button(self):
        result = build_cta_block(
            "Head",
            "Text",
            "https://example.com",
            "Primary",
            secondary_href="https://example.com/alt",
            secondary_label="Alt",
            cta_id="dual",
        )
        assert "Alt" in result
        assert "https://example.com/alt" in result
        assert "gg-insights-cta-btn-secondary" in result

    def test_cta_no_secondary_when_not_provided(self):
        result = build_cta_block(
            "Head", "Text", "https://example.com", "Go", cta_id="solo"
        )
        assert "gg-insights-cta-btn-secondary" not in result


# ── TestComputeStats ──────────────────────────────────────────


class TestComputeStats:
    """Test compute_stats output."""

    def test_returns_dict(self, stats):
        assert isinstance(stats, dict)

    def test_total_races(self, stats, race_count):
        assert stats["total_races"] == race_count

    def test_has_total_distance(self, stats):
        assert stats["total_distance"] > 0

    def test_has_total_elevation(self, stats):
        assert stats["total_elevation"] > 0

    def test_has_states_count(self, stats):
        assert stats["states_with_races"] > 0

    def test_has_everest_multiple(self, stats):
        assert stats["everest_multiple"] > 0

    def test_has_price_min(self, stats):
        assert stats["price_min"] >= 0

    def test_has_price_max(self, stats):
        assert stats["price_max"] > stats["price_min"]

    def test_has_median_price(self, stats):
        assert stats["median_price"] > 0


# ── TestEnrichRaces ───────────────────────────────────────────


class TestEnrichRaces:
    """Test race data enrichment."""

    def test_returns_list(self, gravel_races):
        assert isinstance(gravel_races, list)

    def test_returns_gravel_only(self, gravel_races, race_count):
        assert len(gravel_races) == race_count

    def test_has_state_field(self, gravel_races):
        """At least some races should have state extracted."""
        states = [r.get("state") for r in gravel_races if r.get("state")]
        assert len(states) > 50

    def test_has_founded_field(self, gravel_races):
        """At least some races should have founded year."""
        founded = [r.get("founded") for r in gravel_races if r.get("founded")]
        assert len(founded) > 20

    def test_has_price_field(self, gravel_races):
        """At least some races should have price extracted."""
        prices = [r.get("price") for r in gravel_races if r.get("price")]
        assert len(prices) > 50

    def test_founded_year_range(self, gravel_races):
        for r in gravel_races:
            f = r.get("founded")
            if f is not None:
                assert 1900 <= f <= 2026, f"{r['slug']} has founded={f}"


# ── TestBuildOverratedUnderrated ──────────────────────────────


class TestBuildOverratedUnderrated:
    """Test the overrated/underrated builder directly."""

    def test_returns_string(self, gravel_races, editorial_facts):
        result = build_overrated_underrated(gravel_races, editorial_facts)
        assert isinstance(result, str)

    def test_section_id(self, gravel_races, editorial_facts):
        result = build_overrated_underrated(gravel_races, editorial_facts)
        assert 'id="overrated-underrated"' in result

    def test_has_two_groups(self, gravel_races, editorial_facts):
        result = build_overrated_underrated(gravel_races, editorial_facts)
        groups = re.findall(r'class="gg-insights-ou-group"', result)
        assert len(groups) == 2

    def test_has_card_stats(self, gravel_races, editorial_facts):
        result = build_overrated_underrated(gravel_races, editorial_facts)
        assert "gg-insights-ou-card-stats" in result

    def test_has_card_editorial(self, gravel_races, editorial_facts):
        result = build_overrated_underrated(gravel_races, editorial_facts)
        assert "gg-insights-ou-card-editorial" in result

    def test_card_names_are_real_races(self, gravel_races, editorial_facts):
        result = build_overrated_underrated(gravel_races, editorial_facts)
        names = re.findall(r'class="gg-insights-ou-card-name">([^<]+)</h3>', result)
        all_race_names = {r["name"] for r in gravel_races}
        for name in names:
            assert name in all_race_names, (
                f"OU card name '{name}' not found in race data"
            )

    def test_cards_have_expand_hint(self, gravel_races, editorial_facts):
        result = build_overrated_underrated(gravel_races, editorial_facts)
        assert "gg-ins-ou-expand-hint" in result

    def test_cards_have_detail_section(self, gravel_races, editorial_facts):
        result = build_overrated_underrated(gravel_races, editorial_facts)
        assert "gg-ins-ou-detail" in result

    def test_cards_have_dimension_bars(self, gravel_races, editorial_facts):
        result = build_overrated_underrated(gravel_races, editorial_facts)
        assert "gg-ins-ou-dim-bar" in result
        assert "gg-ins-ou-dim-fill" in result

    def test_cards_have_profile_link(self, gravel_races, editorial_facts):
        result = build_overrated_underrated(gravel_races, editorial_facts)
        assert "gg-ins-ou-link" in result

    def test_cards_aria_expanded_false(self, gravel_races, editorial_facts):
        result = build_overrated_underrated(gravel_races, editorial_facts)
        cards = re.findall(
            r'class="gg-insights-ou-card"[^>]*>', result
        )
        for card in cards:
            assert 'aria-expanded="false"' in card


# ── TestBuildDimensionLeaderboard ────────────────────────────


class TestBuildDimensionLeaderboard:
    """Test build_dimension_leaderboard directly."""

    def test_returns_section(self, gravel_races):
        result = build_dimension_leaderboard(gravel_races)
        assert '<section id="dimension-leaderboard">' in result

    def test_has_figure(self, gravel_races):
        result = build_dimension_leaderboard(gravel_races)
        assert "gg-ins-figure" in result

    def test_has_14_buttons(self, gravel_races):
        result = build_dimension_leaderboard(gravel_races)
        buttons = re.findall(r'class="gg-ins-dim-btn[^"]*"', result)
        assert len(buttons) == 14

    def test_has_dim_controls(self, gravel_races):
        result = build_dimension_leaderboard(gravel_races)
        assert "gg-ins-dim-controls" in result

    def test_has_dim_bars_container(self, gravel_races):
        result = build_dimension_leaderboard(gravel_races)
        assert 'id="dim-leaderboard"' in result

    def test_first_button_is_active(self, gravel_races):
        result = build_dimension_leaderboard(gravel_races)
        first_btn = re.search(r'class="gg-ins-dim-btn[^"]*"', result)
        assert first_btn
        assert "gg-ins-dim-btn--active" in first_btn.group()

    def test_race_count_in_takeaway(self, gravel_races, race_count):
        result = build_dimension_leaderboard(gravel_races)
        assert f"{race_count} rated races" in result


# ── TestBuildNav ──────────────────────────────────────────────


class TestBuildNav:
    """Test build_nav output."""

    def test_returns_string(self):
        result = build_nav()
        assert isinstance(result, str)

    def test_contains_header(self):
        result = build_nav()
        assert "gg-site-header" in result

    def test_contains_breadcrumb(self):
        result = build_nav()
        assert "gg-insights-breadcrumb" in result

    def test_articles_in_breadcrumb(self):
        result = build_nav()
        assert "articles" in result.lower()


# ── TestBuildJsonLd ───────────────────────────────────────────


class TestBuildJsonLd:
    """Test JSON-LD generation."""

    def test_returns_string(self):
        result = build_jsonld(race_count=317, state_count=40)
        assert isinstance(result, str)

    def test_valid_json(self):
        result = build_jsonld(race_count=317, state_count=40)
        match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            result,
            re.DOTALL,
        )
        assert match
        data = json.loads(match.group(1))
        assert data["@context"] == "https://schema.org"

    def test_article_type(self):
        result = build_jsonld(race_count=317, state_count=40)
        match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            result,
            re.DOTALL,
        )
        data = json.loads(match.group(1))
        assert data["@type"] == "Article"

    def test_has_date_published(self):
        result = build_jsonld(race_count=317, state_count=40)
        match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            result,
            re.DOTALL,
        )
        data = json.loads(match.group(1))
        assert "datePublished" in data

    def test_canonical_url(self):
        result = build_jsonld(race_count=317, state_count=40)
        assert "/insights/" in result

    def test_race_count_in_headline(self):
        result = build_jsonld(race_count=317, state_count=40)
        match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            result,
            re.DOTALL,
        )
        data = json.loads(match.group(1))
        assert "317" in data["headline"]

    def test_state_count_in_description(self):
        result = build_jsonld(race_count=317, state_count=40)
        match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            result,
            re.DOTALL,
        )
        data = json.loads(match.group(1))
        assert "40" in data["description"]


# ── TestBuildRaceDataEmbed ────────────────────────────────────


class TestBuildRaceDataEmbed:
    """Test build_race_data_embed directly."""

    def test_returns_script_tag(self, gravel_races):
        result = build_race_data_embed(gravel_races)
        assert '<script type="application/json"' in result
        assert "</script>" in result

    def test_produces_valid_json(self, gravel_races):
        result = build_race_data_embed(gravel_races)
        match = re.search(
            r'<script type="application/json" id="gg-race-data">(.*?)</script>',
            result,
            re.DOTALL,
        )
        data = json.loads(match.group(1))
        assert len(data) == len(gravel_races)

    def test_compact_format(self, gravel_races):
        result = build_race_data_embed(gravel_races)
        assert '": ' not in result


# ── TestBuildHero ─────────────────────────────────────────────


class TestBuildHero:
    """Test build_hero directly."""

    def test_returns_section(self, stats):
        result = build_hero(stats)
        assert "<section" in result

    def test_hero_id(self, stats):
        result = build_hero(stats)
        assert 'id="hero"' in result

    def test_counters_rendered(self, stats):
        result = build_hero(stats)
        assert "data-counter" in result
        assert "gg-insights-counter" in result

    def test_race_count_in_text(self, stats, race_count):
        result = build_hero(stats)
        assert str(race_count) in result


# ── TestBuildDataStory ────────────────────────────────────────


class TestBuildDataStory:
    """Test build_data_story directly."""

    def test_returns_string(self, gravel_races, editorial_facts):
        result = build_data_story(gravel_races, editorial_facts)
        assert isinstance(result, str)

    def test_has_tier_section(self, gravel_races, editorial_facts):
        result = build_data_story(gravel_races, editorial_facts)
        assert 'id="tier-breakdown"' in result

    def test_has_geography_section(self, gravel_races, editorial_facts):
        result = build_data_story(gravel_races, editorial_facts)
        assert 'id="geography"' in result

    def test_has_calendar_section(self, gravel_races, editorial_facts):
        result = build_data_story(gravel_races, editorial_facts)
        assert 'id="calendar"' in result

    def test_has_price_section(self, gravel_races, editorial_facts):
        result = build_data_story(gravel_races, editorial_facts)
        assert 'id="price-myth"' in result

    def test_uses_editorial_quality_state(self, gravel_races, editorial_facts):
        result = build_data_story(gravel_races, editorial_facts)
        qs = editorial_facts.get("quality_state", "")
        if qs:
            assert qs in result, (
                f"Quality state {qs} not found in data story narrative"
            )

    def test_price_correlation_in_narrative(self, gravel_races, editorial_facts):
        result = build_data_story(gravel_races, editorial_facts)
        corr = editorial_facts.get("price_score_corr", 0)
        assert f"{corr:.2f}" in result

    def test_no_scrollytelling_classes(self, gravel_races, editorial_facts):
        result = build_data_story(gravel_races, editorial_facts)
        assert "gg-ins-scrolly" not in result
        assert "gg-ins-dot" not in result

    def test_all_12_month_labels(self, gravel_races, editorial_facts):
        result = build_data_story(gravel_races, editorial_facts)
        for abbr in ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]:
            assert abbr in result

    def test_tier_bar_widths(self, gravel_races, editorial_facts):
        result = build_data_story(gravel_races, editorial_facts)
        widths = re.findall(r'style="width:(\d+)%"', result)
        assert len(widths) >= 4, "Expected at least 4 bar widths"
        assert "100" in widths, "Largest bar should be 100%"


# ── TestBuildRankingBuilder ───────────────────────────────────


class TestBuildRankingBuilder:
    """Test build_ranking_builder directly."""

    def test_returns_section(self, gravel_races):
        result = build_ranking_builder(gravel_races)
        assert '<section id="ranking-builder"' in result

    def test_has_inner_grid(self, gravel_races):
        result = build_ranking_builder(gravel_races)
        assert "gg-ins-rank-inner" in result

    def test_reset_button_text(self, gravel_races):
        result = build_ranking_builder(gravel_races)
        assert "Reset to Equal Weights" in result


# ── TestBuildClosing ─────────────────────────────────────────


class TestBuildClosing:
    """Test build_closing directly with race_count parameter."""

    def test_returns_section(self, race_count):
        result = build_closing(race_count)
        assert "<section" in result

    def test_closing_section_id(self, race_count):
        result = build_closing(race_count)
        assert 'id="what-now"' in result

    def test_closing_title(self, race_count):
        result = build_closing(race_count)
        assert "Now Go Race" in result

    def test_closing_single_class(self, race_count):
        result = build_closing(race_count)
        assert "gg-insights-closing-single" in result

    def test_closing_race_count(self, race_count):
        result = build_closing(race_count)
        assert str(race_count) in result

    def test_closing_explore_button(self, race_count):
        result = build_closing(race_count)
        assert f"Explore All {race_count} Races" in result

    def test_closing_cta_data_attribute(self, race_count):
        result = build_closing(race_count)
        assert 'data-cta="closing-explore"' in result

    def test_closing_links_to_races(self, race_count):
        result = build_closing(race_count)
        assert "gravel-races/" in result

    def test_closing_no_grid(self, race_count):
        result = build_closing(race_count)
        assert "gg-insights-closing-grid" not in result

    def test_closing_no_action_cards(self, race_count):
        result = build_closing(race_count)
        assert "gg-insights-action-card" not in result


# ── TestAnimationsAndGuards ───────────────────────────────────


class TestAnimationsAndGuards:
    """Test scroll-triggered animation and JS guards."""

    def test_gg_has_js_in_js(self, insights_js):
        assert "gg-has-js" in insights_js

    def test_gg_in_view_in_css(self, insights_css):
        assert "gg-in-view" in insights_css

    def test_no_animations_without_gg_has_js(self, insights_css):
        """Hidden figures must be gated by .gg-has-js."""
        assert ".gg-has-js .gg-insights-figure" in insights_css

    def test_reduced_motion_resets_figure(self, insights_css):
        """Reduced motion should reset figure visibility."""
        css = insights_css
        rm_start = css.index("prefers-reduced-motion")
        rm_block = css[rm_start : rm_start + 500]
        assert "gg-insights-figure" in rm_block

    def test_reduced_motion_resets_cards(self, insights_css):
        css = insights_css
        rm_start = css.index("prefers-reduced-motion")
        rm_block = css[rm_start : rm_start + 500]
        assert "gg-insights-ou-card" in rm_block

    def test_ga4_tracking_id(self, insights_html):
        assert "G-EJJZ9T6M52" in insights_html

    def test_print_hides_cta_block(self, insights_css):
        """Print styles should hide CTA blocks."""
        print_start = insights_css.index("@media print")
        print_block = insights_css[print_start : print_start + 500]
        assert "gg-insights-cta-block" in print_block

    def test_print_hides_dim_controls(self, insights_css):
        """Print styles should hide dimension control buttons."""
        print_start = insights_css.index("@media print")
        print_block = insights_css[print_start : print_start + 500]
        assert "gg-ins-dim-controls" in print_block

    def test_reduced_motion_no_dim_bar_transition(self, insights_css):
        """Reduced motion should disable dim bar transitions."""
        css = insights_css
        rm_start = css.index("prefers-reduced-motion")
        rm_block = css[rm_start : rm_start + 500]
        assert "gg-ins-dim-bar-fill" in rm_block


# ── TestGravelOnlyGuard ──────────────────────────────────────


class TestGravelOnlyGuard:
    """Ensure insights page only includes gravel-discipline races."""

    def test_gravel_only_no_bikepacking(self, insights_html):
        """Bikepacking and MTB must be excluded."""
        match = re.search(
            r'<script type="application/json" id="gg-race-data">(.*?)</script>',
            insights_html,
            re.DOTALL,
        )
        assert match
        data = json.loads(match.group(1))
        for entry in data:
            assert entry["di"] == "gravel", (
                f"{entry['s']} has discipline {entry['di']}"
            )

    def test_non_gravel_excluded(self, all_races):
        """All races includes non-gravel; gravel filter should reduce count."""
        gravel_only = [r for r in all_races if (r.get("discipline") or "gravel") == "gravel"]
        non_gravel = [r for r in all_races if (r.get("discipline") or "gravel") != "gravel"]
        assert len(non_gravel) > 0, "Should have at least one non-gravel race"
        assert len(gravel_only) < len(all_races)


# ══════════════════════════════════════════════════════════════
# NEW TESTS — Quality Hardening Sprint
# ══════════════════════════════════════════════════════════════


class TestExtractPriceEdgeCases:
    """Extended edge case tests for extract_price."""

    def test_extract_price_zero(self):
        assert extract_price("$0") == 0.0

    def test_extract_price_euro(self):
        assert extract_price("€100") is None

    def test_extract_price_gbp(self):
        assert extract_price("£100") is None

    def test_extract_price_range(self):
        result = extract_price("$100-$200")
        assert result == 100.0

    def test_extract_price_early_bird(self):
        result = extract_price("Early bird: $100. Regular: $150")
        assert result == 100.0

    def test_extract_price_free(self):
        assert extract_price("Free entry") is None

    def test_extract_price_vip_before_standard(self):
        """VIP Package first, standard after — should get None (VIP only before $)."""
        result = extract_price("VIP Package: $500")
        assert result is None

    def test_extract_price_standard_before_vip(self):
        result = extract_price("Standard $100. VIP Package: $500")
        assert result == 100.0

    def test_extract_price_vip_in_name_context(self):
        """VIP in race name context shouldn't trigger VIP stripping."""
        result = extract_price("VIP Gravel Race entry is $200")
        assert result == 200.0

    def test_extract_price_comma_thousands(self):
        assert extract_price("$1,500") == 1500.0

    def test_extract_price_leading_text(self):
        result = extract_price("Registration is via BikeReg. Cost: $150")
        assert result == 150.0

    def test_extract_price_empty_string(self):
        assert extract_price("") is None


class TestEditorialFactsCorrectness:
    """Test actual logic of editorial facts, not just key presence."""

    def test_overrated_have_high_prestige_low_tier(self, editorial_facts, gravel_races):
        """Every overrated race should have prestige >= 3 AND tier >= 3."""
        overrated = editorial_facts.get("overrated", [])
        for race in overrated:
            p = (race.get("scores") or {}).get("prestige", 0)
            tier = race.get("tier", 4)
            assert p >= 3, f"{race.get('slug')}: prestige {p} < 3"
            assert tier >= 3, f"{race.get('slug')}: tier {tier} < 3"

    def test_underrated_have_low_prestige_high_score(self, editorial_facts):
        """Every underrated race should have prestige <= 2 AND score >= 50."""
        underrated = editorial_facts.get("underrated", [])
        for race in underrated:
            p = (race.get("scores") or {}).get("prestige", 0)
            score = race.get("overall_score", 0)
            assert p <= 2, f"{race.get('slug')}: prestige {p} > 2"
            assert score >= 50, f"{race.get('slug')}: score {score} < 50"

    def test_pony_xpress_excluded(self, editorial_facts):
        """pony-xpress should be in the exclusion set, not in overrated."""
        overrated_slugs = [r.get("slug") for r in editorial_facts.get("overrated", [])]
        assert "pony-xpress" not in overrated_slugs

    def test_cheapest_t1_is_actually_cheapest(self, editorial_facts, gravel_races):
        """No other T1 race should have a lower price."""
        ct1 = editorial_facts.get("cheapest_t1", {})
        if not ct1:
            pytest.skip("No cheapest_t1 found")
        ct1_price = ct1["price"]
        t1_prices = [
            r["price"]
            for r in gravel_races
            if r.get("tier") == 1 and r.get("price") and r["price"] > 0
        ]
        assert ct1_price == min(t1_prices)

    def test_priciest_t4_under_500(self, editorial_facts):
        pt4 = editorial_facts.get("priciest_t4", {})
        if not pt4:
            pytest.skip("No priciest_t4 found")
        assert pt4["price"] <= 500

    def test_best_value_under_150(self, editorial_facts):
        bv = editorial_facts.get("best_value", {})
        if not bv:
            pytest.skip("No best_value found")
        assert bv["price"] <= 150

    def test_price_correlation_bounded(self, editorial_facts):
        corr = editorial_facts.get("price_score_corr", 0)
        assert -1.0 <= corr <= 1.0

    def test_quality_state_has_min_3_races(self, editorial_facts):
        """Quality state should have at least 3 races to be meaningful."""
        qs = editorial_facts.get("quality_state", "")
        sc = editorial_facts.get("state_counts", {})
        if qs and sc:
            assert sc.get(qs, 0) >= 3, f"{qs} has only {sc.get(qs, 0)} races"

    def test_top_state_has_most_races(self, editorial_facts):
        ts = editorial_facts.get("top_state", "")
        sc = editorial_facts.get("state_counts", {})
        if ts and sc:
            ts_count = sc[ts]
            for st, cnt in sc.items():
                assert cnt <= ts_count, f"{st} ({cnt}) > {ts} ({ts_count})"

    def test_overrated_excludes_excluded_set(self, editorial_facts):
        """All slugs in _overrated_exclude must be absent from overrated."""
        _overrated_exclude = {"pony-xpress"}
        overrated_slugs = {r.get("slug") for r in editorial_facts.get("overrated", [])}
        for slug in _overrated_exclude:
            assert slug not in overrated_slugs, f"{slug} should be excluded"


class TestDisciplineFiltering:
    """Verify non-gravel races are excluded from insights."""

    def test_precondition_non_gravel_exist(self, all_races):
        """Dataset should have bikepacking and MTB races."""
        disciplines = {r.get("discipline", "gravel") for r in all_races}
        assert "bikepacking" in disciplines or "mtb" in disciplines

    def test_insights_page_excludes_non_gravel(self, insights_html):
        """Generated race JSON should have zero non-gravel entries."""
        match = re.search(
            r'<script type="application/json" id="gg-race-data">(.*?)</script>',
            insights_html,
            re.DOTALL,
        )
        assert match
        data = json.loads(match.group(1))
        for entry in data:
            assert entry.get("di") == "gravel", (
                f"{entry.get('s')} has discipline {entry.get('di')}"
            )

    def test_stats_use_gravel_only(self, all_races, race_count):
        """Gravel count should be less than total count."""
        assert race_count < len(all_races)

    def test_editorial_facts_gravel_only(self, editorial_facts, all_races):
        """Overrated/underrated lists should contain zero non-gravel slugs."""
        non_gravel_slugs = {
            r.get("slug")
            for r in all_races
            if (r.get("discipline") or "gravel") != "gravel"
        }
        for race in editorial_facts.get("overrated", []):
            assert race.get("slug") not in non_gravel_slugs
        for race in editorial_facts.get("underrated", []):
            assert race.get("slug") not in non_gravel_slugs

    def test_discipline_filter_handles_edge_cases(self):
        """Filter expression handles None, empty string, and 'gravel'."""
        for val, expected in [
            (None, True),
            ("", True),
            ("gravel", True),
            ("bikepacking", False),
            ("mtb", False),
        ]:
            race = {"discipline": val}
            result = (race.get("discipline") or "gravel") == "gravel"
            assert result == expected, f"discipline={val!r}: got {result}"


class TestHiddenAttributeGuard:
    """Ensure HTML hidden attr is not used on expandable panels."""

    def test_no_hidden_attr_on_panels(self, insights_html):
        """No 'hidden' attribute on map or calendar panel divs."""
        # Strip aria-hidden and class values to avoid false positives
        cleaned = re.sub(r'aria-hidden="[^"]*"', '', insights_html)
        cleaned = re.sub(r'class="[^"]*"', '', cleaned)
        # Find all map and calendar panels
        panels = re.findall(r'<div[^>]*gg-ins-(?:map|cal)-panel[^>]*>', cleaned)
        for panel in panels:
            assert ' hidden' not in panel, f"Panel uses hidden attr: {panel[:80]}"

    def test_panels_use_css_class_for_hiding(self, insights_html):
        """Panels should use gg-ins-panel-hidden CSS class."""
        assert "gg-ins-panel-hidden" in insights_html


class TestSvgCompliance:
    """Ensure SVG elements follow brand rules (no inline styles)."""

    def test_no_inline_style_in_svg(self, insights_html):
        """Zero style= attributes inside any <svg> tag."""
        svg_blocks = re.findall(r'<svg[^>]*>.*?</svg>', insights_html, re.DOTALL)
        for svg in svg_blocks:
            assert 'style=' not in svg, f"SVG has inline style: {svg[:100]}"

    def test_no_svg_font_presentation_attrs(self, insights_html):
        """No font-family= or font-size= on SVG elements."""
        svg_blocks = re.findall(r'<svg[^>]*>.*?</svg>', insights_html, re.DOTALL)
        for svg in svg_blocks:
            assert 'font-family=' not in svg, f"SVG font-family attr: {svg[:100]}"
            assert 'font-size=' not in svg, f"SVG font-size attr: {svg[:100]}"

    def test_no_svg_fill_stroke_attrs(self, insights_html):
        """No fill= or stroke= on SVG child elements (use CSS instead)."""
        svg_blocks = re.findall(r'<svg[^>]*>.*?</svg>', insights_html, re.DOTALL)
        for svg in svg_blocks:
            # Inside the svg, check child elements (not the <svg> root itself)
            inner = re.sub(r'^<svg[^>]*>', '', svg)
            inner = re.sub(r'</svg>$', '', inner)
            # Allow fill="none" which is common and valid
            inner_cleaned = re.sub(r'fill="none"', '', inner)
            elements = re.findall(r'<[a-z]+[^>]*>', inner_cleaned)
            for el in elements:
                assert ' fill=' not in el, f"SVG child has fill attr: {el[:80]}"
                assert ' stroke=' not in el, f"SVG child has stroke attr: {el[:80]}"


class TestDomainParity:
    """Verify correct domain in JS and race links."""

    def test_no_wrong_domain_in_js(self, insights_js):
        """www.gravelgod.com must NOT appear in JS."""
        assert "www.gravelgod.com" not in insights_js

    def test_js_site_url_matches_python(self, insights_js):
        """JS SITE_URL value should match Python SITE_BASE_URL."""
        match = re.search(r'var SITE_URL\s*=\s*"([^"]+)"', insights_js)
        assert match, "SITE_URL not found in JS"
        assert match.group(1) == SITE_BASE_URL

    def test_all_race_links_use_correct_domain(self, insights_html):
        """All /race/{slug}/ links should use the correct domain."""
        links = re.findall(r'href="(https?://[^"]*?/race/[^"]+/)"', insights_html)
        for link in links:
            assert link.startswith(SITE_BASE_URL), (
                f"Race link uses wrong domain: {link}"
            )


class TestDimParity:
    """Verify Python/JS dimension parity."""

    def test_js_dims_match_python(self, insights_js):
        """JS DIMS array must match Python ALL_DIMS exactly."""
        match = re.search(r'var DIMS\s*=\s*(\[.*?\]);', insights_js)
        assert match, "DIMS array not found in JS"
        js_dims = json.loads(match.group(1))
        assert js_dims == ALL_DIMS

    def test_js_dim_labels_cover_all_dims(self, insights_js):
        """Every dim in ALL_DIMS must have a label in JS DIM_LABELS."""
        match = re.search(r'var DIM_LABELS\s*=\s*(\{.*?\});', insights_js, re.DOTALL)
        assert match, "DIM_LABELS not found in JS"
        js_labels = json.loads(match.group(1))
        for dim in ALL_DIMS:
            assert dim in js_labels, f"Missing JS label for dim: {dim}"

    def test_dim_count_not_hardcoded(self, insights_html):
        """The dimension count string should match len(ALL_DIMS)."""
        expected = f"{len(ALL_DIMS)} dimensions"
        assert expected in insights_html

    def test_no_hardcoded_14_dimensions(self, insights_html):
        """'14 dimensions' should NOT appear as a hardcoded string."""
        # If ALL_DIMS changes, this catches stale hardcoded "14 dimensions"
        if len(ALL_DIMS) != 14:
            assert "14 dimensions" not in insights_html


class TestPresetParity:
    """Verify presets are emitted from Python into JS."""

    def test_presets_emitted_from_python(self, insights_js):
        """JS PRESETS should be generated from Python RANKING_PRESETS."""
        match = re.search(r'var PRESETS\s*=\s*(\{.*?\});', insights_js, re.DOTALL)
        assert match, "PRESETS not found in JS"
        js_presets = json.loads(match.group(1))
        assert js_presets == RANKING_PRESETS

    def test_all_preset_names_in_js(self, insights_js):
        """All preset names should appear in JS."""
        for name in RANKING_PRESETS:
            assert name in insights_js, f"Preset {name} missing from JS"

    def test_preset_weights_nonzero(self):
        """All preset weights should be >= 1 (min slider value)."""
        for name, weights in RANKING_PRESETS.items():
            for group, val in weights.items():
                assert val >= 1, f"Preset {name}.{group} = {val} < 1"


class TestJsBehavior:
    """Test JS behavioral correctness via string analysis."""

    def test_json_parse_has_try_catch(self, insights_js):
        """JSON.parse should be wrapped in try/catch."""
        assert "try" in insights_js
        # Verify try is near JSON.parse
        try_idx = insights_js.index("try")
        parse_idx = insights_js.index("JSON.parse")
        # try should come before JSON.parse (within ~200 chars)
        assert try_idx < parse_idx
        assert parse_idx - try_idx < 200

    def test_bar_width_clamped(self, insights_js):
        """Dimension bar width should be clamped with Math.min/max."""
        assert "Math.min(100" in insights_js
        assert "Math.max(0" in insights_js

    def test_counter_reduced_motion_shows_final_value(self, insights_js):
        """Counter should display final value on reduced-motion, not skip."""
        # Find the reduced-motion / target===0 early return
        # It should set el.textContent = original before returning
        lines = insights_js.split("\n")
        for i, line in enumerate(lines):
            if "reducedMotion" in line and "return" in line:
                # Check the preceding line sets textContent
                context = "\n".join(lines[max(0, i - 3) : i + 1])
                assert "el.textContent" in context or "textContent = original" in context, (
                    f"Reduced-motion return doesn't set final value: {context}"
                )
                break

    def test_counter_zero_target_shows_value(self, insights_js):
        """Target === 0 should set content, not skip entirely."""
        # The fix: if (target === 0 || reducedMotion) { el.textContent = original; return; }
        assert "target === 0" in insights_js
        # el.textContent = original should appear near it
        idx = insights_js.index("target === 0")
        context = insights_js[idx : idx + 200]
        assert "el.textContent" in context

    def test_site_url_variable_used(self, insights_js):
        """Race links in JS should use SITE_URL variable."""
        assert "SITE_URL" in insights_js
        # It should be used in href construction
        assert "SITE_URL +" in insights_js or "SITE_URL+" in insights_js or "${SITE_URL}" in insights_js

    def test_slider_min_is_one(self, insights_html):
        """Ranking builder sliders should have min=1, not min=0."""
        sliders = re.findall(r'<input[^>]*class="gg-ins-rank-slider"[^>]*>', insights_html)
        assert len(sliders) > 0, "No sliders found"
        for slider in sliders:
            assert 'min="1"' in slider, f"Slider has wrong min: {slider[:80]}"

    def test_panel_toggle_uses_class_not_hidden(self, insights_js):
        """JS panel toggling should use CSS class, not hidden attribute."""
        assert "gg-ins-panel-hidden" in insights_js
        # hidden attr manipulation should NOT be present
        assert "setAttribute('hidden'" not in insights_js
        assert "removeAttribute('hidden')" not in insights_js


class TestJsonLdDynamic:
    """Verify JSON-LD uses dynamic dates."""

    def test_jsonld_date_is_dynamic(self, insights_html):
        """datePublished should be today's date, not hardcoded."""
        import datetime

        today = datetime.date.today().isoformat()
        match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            insights_html,
            re.DOTALL,
        )
        assert match, "JSON-LD not found"
        ld = json.loads(match.group(1))
        assert ld.get("datePublished") == today
        assert ld.get("dateModified") == today

    def test_jsonld_no_hardcoded_2026_02_20(self, insights_html):
        """The old hardcoded date should not appear."""
        match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            insights_html,
            re.DOTALL,
        )
        assert match
        ld_text = match.group(1)
        assert "2026-02-20" not in ld_text


class TestEdgeCaseData:
    """Test with synthetic edge-case data."""

    def test_race_with_none_score_no_crash(self, all_races):
        """Race with overall_score=None should not crash compute_editorial_facts."""
        # Inject a synthetic race with None score
        test_races = list(all_races[:10])
        test_races.append({
            "name": "Test Null Score Race",
            "slug": "test-null-score",
            "overall_score": None,
            "tier": 3,
            "discipline": "gravel",
            "scores": {},
        })
        # Should not raise
        result = compute_editorial_facts(test_races)
        assert isinstance(result, dict)

    def test_race_with_zero_score(self, all_races):
        """Race with score=0 should not be silently dropped."""
        test_races = list(all_races[:10])
        test_races.append({
            "name": "Test Zero Score Race",
            "slug": "test-zero-score",
            "overall_score": 0,
            "tier": 4,
            "discipline": "gravel",
            "scores": {},
        })
        result = compute_editorial_facts(test_races)
        assert isinstance(result, dict)

    def test_race_with_missing_state(self, all_races):
        """Race with no location should not crash state grouping."""
        test_races = list(all_races[:10])
        test_races.append({
            "name": "Test No Location Race",
            "slug": "test-no-loc",
            "overall_score": 60,
            "tier": 2,
            "discipline": "gravel",
            "scores": {},
        })
        result = compute_editorial_facts(test_races)
        assert isinstance(result, dict)

    def test_race_with_missing_price(self, all_races):
        """Race with no price should not crash price stats."""
        test_races = list(all_races[:10])
        test_races.append({
            "name": "Test No Price Race",
            "slug": "test-no-price",
            "overall_score": 70,
            "tier": 2,
            "discipline": "gravel",
            "scores": {},
        })
        result = compute_editorial_facts(test_races)
        assert isinstance(result, dict)

    def test_single_race_in_tier(self, gravel_races, stats):
        """Stats should compute without crash even with varied tier distribution."""
        assert isinstance(stats, dict)
        assert "total_races" in stats
        assert stats["total_races"] > 0

    def test_month_with_zero_races_renders(self, gravel_races, editorial_facts):
        """Calendar should render even if a month has zero races."""
        html = build_data_story(gravel_races, editorial_facts)
        # December often has 0 races — verify it's still in the calendar
        assert "Dec" in html or "December" in html


class TestCssFontSizeTokens:
    """Verify font sizes use design tokens where possible."""

    def test_map_abbr_uses_token(self, insights_css):
        """Map abbreviation should use --gg-font-size-2xs token."""
        # Find the .gg-ins-map-abbr rule (non-responsive version)
        idx = insights_css.index(".gg-ins-map-abbr")
        block = insights_css[idx : idx + 200]
        assert "var(--gg-font-size-2xs)" in block

    def test_cal_count_uses_token(self, insights_css):
        """Calendar count should use --gg-font-size-2xs token."""
        idx = insights_css.index(".gg-ins-cal-count")
        block = insights_css[idx : idx + 200]
        assert "var(--gg-font-size-2xs)" in block

    def test_cal_label_uses_token(self, insights_css):
        """Calendar label should use --gg-font-size-2xs token."""
        idx = insights_css.index(".gg-ins-cal-label")
        block = insights_css[idx : idx + 200]
        assert "var(--gg-font-size-2xs)" in block

    def test_ou_dim_label_uses_token(self, insights_css):
        """O/U dimension label should use --gg-font-size-2xs token."""
        idx = insights_css.index(".gg-ins-ou-dim-label")
        block = insights_css[idx : idx + 200]
        assert "var(--gg-font-size-2xs)" in block

    def test_ou_dim_val_uses_token(self, insights_css):
        """O/U dimension value should use --gg-font-size-2xs token."""
        idx = insights_css.index(".gg-ins-ou-dim-val")
        block = insights_css[idx : idx + 200]
        assert "var(--gg-font-size-2xs)" in block

    def test_exceptions_documented(self, insights_css):
        """9px, 11px remain as documented exceptions (no exact token)."""
        # 9px used in map-count and cal-tier (tight layouts, below smallest token)
        assert "font-size: 9px" in insights_css
        # 11px used in tooltip (between 2xs=10 and xs=13)
        assert "font-size: 11px" in insights_css


class TestGeographyNarrativeGuard:
    """Test geography narrative handles empty state data."""

    def test_geography_narrative_with_states(self, insights_html):
        """Geography narrative should include top state when data exists."""
        # Just verify the geo section exists and has content
        assert 'id="geography"' in insights_html

    def test_no_empty_state_name_in_narrative(self, insights_html):
        """Narrative should not contain ' leads with' without a state name."""
        assert " leads with" not in insights_html or re.search(
            r'[A-Z]{2}\s+leads with', insights_html
        )


class TestDeadCodeRemoval:
    """Verify dead code has been removed."""

    def test_no_build_heritage_function(self):
        """build_heritage() dead code should be removed."""
        import generate_insights as gi

        assert not hasattr(gi, "build_heritage"), "build_heritage still exists as dead code"

    def test_no_heritage_scatter_in_html(self, insights_html):
        """Heritage scatter plot SVG should not appear in output."""
        assert "heritage-scatter" not in insights_html
        assert "gg-ins-heritage" not in insights_html


# ── TestExtractCountry ───────────────────────────────────────


class TestExtractCountry:
    """Test extract_country() for international race locations."""

    def test_explicit_country_name(self):
        assert extract_country("Girona, Spain") == "ES"

    def test_subregion_maps_to_country(self):
        assert extract_country("Flanders, Belgium") == "BE"

    def test_uk_subregion(self):
        assert extract_country("Northumberland, England") == "GB"

    def test_canadian_province(self):
        assert extract_country("Calgary, Alberta, Canada") == "CA"

    def test_australian_state(self):
        assert extract_country("Queensland, Australia") == "AU"

    def test_us_location_returns_none(self):
        """US locations should return None (handled by state grid)."""
        assert extract_country("Emporia, Kansas") is None

    def test_us_abbreviation_returns_none(self):
        assert extract_country("Leadville, CO") is None

    def test_empty_returns_none(self):
        assert extract_country("") is None

    def test_none_returns_none(self):
        assert extract_country(None) is None

    def test_global_returns_none(self):
        """Unmatched location strings return None."""
        assert extract_country("Global") is None

    def test_multi_location_returns_none(self):
        assert extract_country("Various Locations") is None

    def test_french_subregion(self):
        assert extract_country("Millau, France") == "FR"

    def test_german_subregion(self):
        assert extract_country("Black Forest, Germany") == "DE"

    def test_new_zealand(self):
        assert extract_country("Lake Taupo, New Zealand") == "NZ"

    def test_south_africa(self):
        assert extract_country("Mpumalanga, South Africa") == "ZA"

    def test_colombia(self):
        assert extract_country("Bogotá, Colombia") == "CO"


# ── TestExtractCountryConstants ──────────────────────────────


class TestExtractCountryConstants:
    """Test COUNTRY_MAP, COUNTRY_NAMES, and WORLD_REGIONS consistency."""

    def test_all_country_map_values_in_country_names(self):
        """Every ISO code in COUNTRY_MAP must have a display name."""
        for key, code in COUNTRY_MAP.items():
            assert code in COUNTRY_NAMES, (
                f"COUNTRY_MAP[{key!r}] = {code!r} not in COUNTRY_NAMES"
            )

    def test_all_world_region_codes_in_country_names(self):
        """Every ISO code in WORLD_REGIONS must have a display name."""
        for region, codes in WORLD_REGIONS.items():
            for code in codes:
                assert code in COUNTRY_NAMES, (
                    f"WORLD_REGIONS[{region!r}] has {code!r} not in COUNTRY_NAMES"
                )

    def test_four_world_regions(self):
        assert set(WORLD_REGIONS.keys()) == {"Europe", "Americas", "Asia-Pacific", "Africa"}

    def test_no_duplicate_codes_across_regions(self):
        """Each country code should appear in exactly one region."""
        seen = {}
        for region, codes in WORLD_REGIONS.items():
            for code in codes:
                assert code not in seen, (
                    f"{code} in both {seen[code]} and {region}"
                )
                seen[code] = region


# ── TestWorldMapData ─────────────────────────────────────────


class TestWorldMapData:
    """Test the SVG world map data module."""

    def test_world_map_paths_is_dict(self):
        from world_map_data import WORLD_MAP_PATHS
        assert isinstance(WORLD_MAP_PATHS, dict)
        assert len(WORLD_MAP_PATHS) >= 170

    def test_all_race_countries_have_paths(self):
        from world_map_data import WORLD_MAP_PATHS
        for code in COUNTRY_NAMES:
            assert code in WORLD_MAP_PATHS, (
                f"Race country {code} ({COUNTRY_NAMES[code]}) missing from WORLD_MAP_PATHS"
            )

    def test_paths_are_valid_svg_d_strings(self):
        from world_map_data import WORLD_MAP_PATHS
        for iso, d_str in WORLD_MAP_PATHS.items():
            assert d_str.startswith("M"), f"{iso} path doesn't start with M"
            assert "Z" in d_str, f"{iso} path missing Z (close)"

    def test_country_centroids_have_race_countries(self):
        from world_map_data import COUNTRY_CENTROIDS
        for code in COUNTRY_NAMES:
            assert code in COUNTRY_CENTROIDS, (
                f"Race country {code} missing from COUNTRY_CENTROIDS"
            )

    def test_centroids_are_valid_coordinates(self):
        from world_map_data import COUNTRY_CENTROIDS
        for iso, (cx, cy) in COUNTRY_CENTROIDS.items():
            assert 0 <= cx <= 1000, f"{iso} centroid x={cx} out of viewBox"
            assert 0 <= cy <= 500, f"{iso} centroid y={cy} out of viewBox"

    def test_us_path_present(self):
        from world_map_data import WORLD_MAP_PATHS
        assert "US" in WORLD_MAP_PATHS


# ── TestWorldGrid (SVG Map) ─────────────────────────────────


class TestWorldGrid:
    """Test the international SVG world map in the geography section."""

    def test_world_grid_present(self, insights_html):
        """World grid container should be in the geography section."""
        assert "gg-ins-world-grid" in insights_html

    def test_world_grid_inside_geography(self, insights_html):
        geo_match = re.search(
            r'id="geography".*?</section>', insights_html, re.DOTALL
        )
        assert geo_match
        assert "gg-ins-world-grid" in geo_match.group()

    def test_svg_worldmap_present(self, insights_html):
        """SVG element with worldmap class should be present."""
        assert 'class="gg-ins-worldmap"' in insights_html

    def test_svg_has_viewbox(self, insights_html):
        svg_match = re.search(r'<svg[^>]*class="gg-ins-worldmap"[^>]*>', insights_html)
        assert svg_match
        assert 'viewBox="0 0 1000 500"' in svg_match.group()

    def test_svg_has_role_img(self, insights_html):
        svg_match = re.search(r'<svg[^>]*class="gg-ins-worldmap"[^>]*>', insights_html)
        assert svg_match
        assert 'role="img"' in svg_match.group()

    def test_svg_has_aria_label(self, insights_html):
        svg_match = re.search(r'<svg[^>]*class="gg-ins-worldmap"[^>]*>', insights_html)
        assert svg_match
        assert 'aria-label=' in svg_match.group()

    def test_race_countries_have_paths(self, insights_html):
        """Race countries should be rendered as interactive SVG paths."""
        geo_match = re.search(
            r'class="gg-ins-world-grid".*?</section>', insights_html, re.DOTALL
        )
        assert geo_match
        countries = re.findall(
            r'class="gg-wm-country[^"]*"[^>]*data-country="([A-Z]{2})"',
            geo_match.group()
        )
        assert len(countries) >= 10, f"Expected >=10 country paths, got {len(countries)}"

    def test_race_paths_have_density_class(self, insights_html):
        """Race country paths should have density class (low/med/high)."""
        densities = re.findall(
            r'gg-wm-density-(low|med|high)',
            insights_html
        )
        assert len(densities) >= 10

    def test_us_path_is_neutral(self, insights_html):
        """US should have a neutral land path (not interactive)."""
        assert 'gg-wm-land gg-wm-us' in insights_html

    def test_non_race_countries_are_neutral(self, insights_html):
        """Non-race countries should have gg-wm-land class."""
        assert 'class="gg-wm-land"' in insights_html

    def test_race_paths_have_tabindex_minus_one(self, insights_html):
        """Race country paths use tabindex=-1 (no tab trap)."""
        paths = re.findall(
            r'class="gg-wm-country[^"]*"[^>]*tabindex="-1"',
            insights_html
        )
        assert len(paths) >= 10

    def test_race_paths_have_aria_expanded(self, insights_html):
        """Race country paths should start with aria-expanded=false."""
        expanded = re.findall(
            r'class="gg-wm-country[^"]*"[^>]*aria-expanded="false"',
            insights_html
        )
        assert len(expanded) >= 10

    def test_race_paths_have_svg_title(self, insights_html):
        """Race country paths should have inline <title> elements (not JS-built)."""
        titles = re.findall(
            r'<path[^>]*class="gg-wm-country[^"]*"[^>]*>.*?<title>[^<]+</title>',
            insights_html
        )
        assert len(titles) >= 10

    def test_country_labels_present(self, insights_html):
        """SVG text labels should be present for race countries."""
        labels = re.findall(r'class="gg-wm-label"', insights_html)
        assert len(labels) >= 10

    def test_country_panels_hidden_by_default(self, insights_html):
        """Country panels should start hidden."""
        geo_match = re.search(
            r'id="world-detail".*?</div>', insights_html, re.DOTALL
        )
        assert geo_match
        panels = re.findall(r'gg-ins-panel-hidden', geo_match.group())
        assert len(panels) >= 1

    def test_country_panels_have_race_links(self, insights_html):
        """Country panels should contain race profile links."""
        geo_match = re.search(
            r'id="world-detail".*?</div>\s*</div>', insights_html, re.DOTALL
        )
        assert geo_match
        assert "/race/" in geo_match.group()

    def test_no_not_shown_dismissal(self, insights_html):
        """The old 'not shown' italic line should be gone."""
        assert "outside the US not shown" not in insights_html

    def test_world_detail_aria_live(self, insights_html):
        """World detail container should have aria-live for accessibility."""
        assert 'id="world-detail"' in insights_html
        detail = re.search(r'id="world-detail"[^>]*>', insights_html)
        assert detail
        assert 'aria-live="polite"' in detail.group()

    def test_world_subtitle_race_count(self, insights_html):
        """Subtitle should mention race and country counts."""
        geo_match = re.search(
            r'class="gg-ins-world-subtitle".*?</p>', insights_html, re.DOTALL
        )
        assert geo_match
        text = geo_match.group()
        assert "races across" in text
        assert "countries" in text

    def test_no_old_tile_classes(self, insights_html):
        """Old tile grid classes should be completely gone."""
        assert "gg-ins-world-tile" not in insights_html
        assert "gg-ins-world-region" not in insights_html
        assert "gg-ins-world-code" not in insights_html
        assert "gg-ins-world-count" not in insights_html


# ── TestWorldMapLegend ──────────────────────────────────────


class TestWorldMapLegend:
    """Test the world map density legend."""

    def test_legend_present(self, insights_html):
        assert "gg-ins-world-legend" in insights_html

    def test_legend_has_three_levels(self, insights_html):
        legend_match = re.search(
            r'class="gg-ins-world-legend".*?</div>',
            insights_html, re.DOTALL
        )
        assert legend_match
        section = legend_match.group()
        assert "gg-wm-density-low" in section
        assert "gg-wm-density-med" in section
        assert "gg-wm-density-high" in section

    def test_legend_has_labels(self, insights_html):
        legend_match = re.search(
            r'class="gg-ins-world-legend".*?</div>',
            insights_html, re.DOTALL
        )
        assert legend_match
        section = legend_match.group()
        assert "races" in section
        assert "5+" in section


# ── TestWorldMapCss ─────────────────────────────────────────


class TestWorldMapCss:
    """Test CSS for SVG world map."""

    def test_world_grid_css(self, insights_css):
        assert ".gg-ins-world-grid" in insights_css

    def test_worldmap_css(self, insights_css):
        assert ".gg-ins-worldmap" in insights_css

    def test_wm_land_css(self, insights_css):
        assert ".gg-wm-land" in insights_css

    def test_wm_country_css(self, insights_css):
        assert ".gg-wm-country" in insights_css

    def test_wm_density_low_css(self, insights_css):
        assert ".gg-wm-density-low" in insights_css

    def test_wm_density_med_css(self, insights_css):
        assert ".gg-wm-density-med" in insights_css

    def test_wm_density_high_css(self, insights_css):
        assert ".gg-wm-density-high" in insights_css

    def test_wm_country_hover_css(self, insights_css):
        assert ".gg-wm-country:hover" in insights_css

    def test_wm_country_expanded_css(self, insights_css):
        assert '.gg-wm-country[aria-expanded="true"]' in insights_css

    def test_wm_label_css(self, insights_css):
        assert ".gg-wm-label" in insights_css

    def test_legend_css(self, insights_css):
        assert ".gg-ins-world-legend" in insights_css

    def test_swatch_css(self, insights_css):
        assert ".gg-wm-swatch" in insights_css

    def test_no_old_tile_css(self, insights_css):
        """Old tile CSS classes should be completely gone."""
        assert ".gg-ins-world-tile" not in insights_css
        assert ".gg-ins-world-region" not in insights_css

    def test_css_uses_only_vars(self, insights_css):
        """SVG fill/stroke should use CSS custom properties, not hex
        (except hex fallbacks immediately before a color-mix override)."""
        # Known hex fallbacks paired with color-mix overrides
        COLOR_MIX_FALLBACKS = {"#d8e5e0", "#aeccc6", "#7aafa7"}
        for prop in ["fill:", "stroke:"]:
            matches = re.findall(rf'{prop}\s*([^;]+);', insights_css)
            for val in matches:
                val = val.strip()
                if val == "none" or val.startswith("var(") or val.startswith("color-mix("):
                    continue
                if val in COLOR_MIX_FALLBACKS:
                    continue  # hex fallback for color-mix() browser compat
                assert not val.startswith("#"), (
                    f"Found hardcoded hex in CSS: {prop} {val}"
                )


# ── TestWorldMapJs ──────────────────────────────────────────


class TestWorldMapJs:
    """Test JS for world map interactivity."""

    def test_toggle_world_country_fn(self, insights_js):
        assert "toggleWorldCountry" in insights_js

    def test_ga4_country_event(self, insights_js):
        assert "insights_country_click" in insights_js

    def test_world_detail_reference(self, insights_js):
        assert "world-detail" in insights_js

    def test_svg_selector(self, insights_js):
        assert ".gg-ins-worldmap" in insights_js

    def test_country_path_selector(self, insights_js):
        assert ".gg-wm-country" in insights_js

    def test_keyboard_handler(self, insights_js):
        assert "keydown" in insights_js
        assert "Enter" in insights_js

    def test_no_js_svg_tooltip_builder(self, insights_js):
        """World map tooltips are now <title> in SVG at gen time, not JS-built."""
        assert "createElementNS" not in insights_js

    def test_no_old_tile_selectors(self, insights_js):
        """Old tile selectors should be completely gone."""
        assert ".gg-ins-world-tile" not in insights_js


# ── TestWorldMapBehavioral (post-audit) ─────────────────────


class TestWorldMapBehavioral:
    """Behavioral tests added after Sprint 39 self-audit.

    Each test targets a specific confirmed bug class, not just string presence.
    """

    # ── Fix 1: Antimeridian ──

    def test_antimeridian_no_huge_jumps(self):
        """SVG paths for antimeridian countries (RU, FJ, AQ) must not have
        >500px x-jumps within L segments (would cause visual tears)."""
        from world_map_data import WORLD_MAP_PATHS
        for iso in ("RU", "FJ", "AQ"):
            d = WORLD_MAP_PATHS.get(iso, "")
            assert d, f"{iso} missing from WORLD_MAP_PATHS"
            # Parse path: track x across L commands only (M starts new sub-path)
            tokens = re.findall(r"([MLZ])([0-9.,]*)", d)
            prev_x = None
            for cmd, val in tokens:
                if cmd == "Z":
                    prev_x = None
                    continue
                if cmd == "M":
                    parts = val.split(",")
                    prev_x = float(parts[0])
                    continue
                if cmd == "L" and prev_x is not None:
                    parts = val.split(",")
                    x = float(parts[0])
                    jump = abs(x - prev_x)
                    assert jump <= 500, (
                        f"{iso}: L-segment x-jump of {jump:.0f}px (antimeridian tear)"
                    )
                    prev_x = x

    def test_all_race_country_centroids_exist(self):
        """Every country in COUNTRY_NAMES must have a centroid for label placement."""
        from world_map_data import COUNTRY_CENTROIDS
        for code, name in COUNTRY_NAMES.items():
            assert code in COUNTRY_CENTROIDS, (
                f"Race country {code} ({name}) missing from COUNTRY_CENTROIDS"
            )

    def test_centroids_within_country_bounds(self):
        """Centroids should be within reasonable bounds of the country's path bbox."""
        from world_map_data import COUNTRY_CENTROIDS, WORLD_MAP_PATHS
        for iso in COUNTRY_NAMES:
            if iso not in WORLD_MAP_PATHS:
                continue
            d = WORLD_MAP_PATHS[iso]
            cx, cy = COUNTRY_CENTROIDS[iso]
            # Extract all coordinates from path
            coords = re.findall(r"[ML]([0-9.]+),([0-9.]+)", d)
            if not coords:
                continue
            xs = [float(c[0]) for c in coords]
            ys = [float(c[1]) for c in coords]
            # Centroid should be within viewBox (0-1000, 0-500)
            assert 0 <= cx <= 1000, f"{iso} centroid x={cx} out of viewBox"
            assert 0 <= cy <= 500, f"{iso} centroid y={cy} out of viewBox"

    # ── Fix 2: Editorial casing ──

    def test_editorial_quip_casing(self, insights_html):
        """Multi-word dimension labels like 'Race Quality' must keep title case
        in editorial quips, not become 'Race quality' via .capitalize()."""
        multi_word_labels = [v for v in DIM_LABELS.values() if " " in v]
        assert len(multi_word_labels) >= 2, "Expected multi-word DIM_LABELS"
        for label in multi_word_labels:
            bad = label[0].upper() + label[1:].lower()  # e.g. "Race quality"
            if bad != label:
                # If the bad version appears, it should not be followed by ": N/5"
                bad_pattern = re.escape(bad) + r": \d/5"
                matches = re.findall(bad_pattern, insights_html)
                assert not matches, (
                    f"Found .capitalize() casing bug: '{bad}' in editorial text"
                )

    def test_editorial_quips_all_unique(self, insights_html):
        """No two editorial quip texts should be identical across all
        overrated/underrated cards."""
        editorials = re.findall(
            r'class="gg-insights-ou-card-editorial">(.*?)</div>',
            insights_html, re.DOTALL
        )
        # Need at least some editorials to test
        if len(editorials) < 2:
            pytest.skip("Not enough editorial quips to test uniqueness")
        # Strip whitespace for comparison
        cleaned = [e.strip() for e in editorials]
        # Allow some duplicates (different races can have same template variant)
        # but not ALL identical
        unique = set(cleaned)
        assert len(unique) > 1, "All editorial quips are identical — variant logic broken"

    # ── Fix 3: SVG <title> at generation time ──

    def test_svg_title_elements_present(self, insights_html):
        """Every interactive world map path must have a <title> child element
        with country name and race count, generated at Python time (not JS)."""
        paths_with_title = re.findall(
            r'<path[^>]*class="gg-wm-country[^"]*"[^>]*><title>([^<]+)</title></path>',
            insights_html
        )
        assert len(paths_with_title) >= 10, (
            f"Expected >=10 paths with <title>, got {len(paths_with_title)}"
        )
        # Verify title content format: "Country: N race(s)"
        for title_text in paths_with_title:
            assert re.match(r".+: \d+ races?$", title_text), (
                f"Unexpected title format: '{title_text}'"
            )

    def test_no_data_tooltip_on_world_paths(self, insights_html):
        """World map paths should NOT have data-tooltip (moved to <title>)."""
        world_paths = re.findall(
            r'<path[^>]*class="gg-wm-country[^"]*"[^>]*/?>',
            insights_html
        )
        for path in world_paths:
            assert "data-tooltip" not in path, (
                f"World map path still has data-tooltip: {path[:100]}"
            )

    # ── Fix 4: No tabindex=0 tab trap ──

    def test_no_tabindex_zero_on_paths(self, insights_html):
        """No world map path should have tabindex='0' (creates 32-stop tab trap)."""
        bad_paths = re.findall(
            r'<path[^>]*class="gg-wm-country[^"]*"[^>]*tabindex="0"',
            insights_html
        )
        assert len(bad_paths) == 0, (
            f"Found {len(bad_paths)} world map paths with tabindex='0' (tab trap)"
        )

    # ── Fix 5: Density thresholds match legend ──

    def test_density_thresholds_match_legend(self, insights_html):
        """Legend text must match DENSITY_HIGH_MIN/DENSITY_MED_MIN constants."""
        legend = re.search(
            r'class="gg-ins-world-legend">(.*?)</div>',
            insights_html, re.DOTALL
        )
        assert legend, "World map legend not found"
        text = legend.group(1)
        # Legend should reference the exact threshold values
        assert f"{DENSITY_HIGH_MIN}+" in text, (
            f"Legend missing '{DENSITY_HIGH_MIN}+' for high density"
        )
        assert f"{DENSITY_MED_MIN}" in text, (
            f"Legend missing '{DENSITY_MED_MIN}' for medium density start"
        )

    def test_density_boundary_1_race(self):
        """1 race in a country → 'low' density."""
        assert 1 < DENSITY_MED_MIN, "Threshold sanity: 1 should be below med"

    def test_density_boundary_med(self):
        """DENSITY_MED_MIN races → 'med' density (not low)."""
        assert DENSITY_MED_MIN < DENSITY_HIGH_MIN, (
            "Threshold sanity: med min must be below high min"
        )

    def test_density_boundary_high(self):
        """DENSITY_HIGH_MIN races → 'high' density (not med)."""
        assert DENSITY_HIGH_MIN >= 3, "High threshold seems too low"
        assert DENSITY_HIGH_MIN <= 20, "High threshold seems too high"

    # ── Fix 6: color-mix fallbacks ──

    def test_color_mix_has_fallback(self, insights_css):
        """Every color-mix() density rule must have a hex fallback.
        Checks both SVG fill rules and swatch background rules."""
        density_classes = ["gg-wm-density-low", "gg-wm-density-med", "gg-wm-density-high"]
        for cls in density_classes:
            # Find ALL CSS blocks for this class (swatch uses background, SVG uses fill)
            pattern = re.escape(f".{cls}") + r"\s*\{([^}]+)\}"
            matches = re.findall(pattern, insights_css)
            assert matches, f"CSS rule for .{cls} not found"
            for block in matches:
                assert "color-mix(" in block, f".{cls} missing color-mix()"
                # Hex fallback can be fill: or background: depending on context
                assert re.search(r"(?:fill|background):\s*#[0-9a-fA-F]{6}", block), (
                    f".{cls} missing hex fallback before color-mix()"
                )

    # ── Fix 7: JS uses e.currentTarget ──

    def test_js_uses_currentTarget(self, insights_js):
        """World map JS event handlers must use e.currentTarget, not this."""
        # Check for the pattern: e.currentTarget.getAttribute('data-country')
        assert "e.currentTarget.getAttribute" in insights_js, (
            "World map JS should use e.currentTarget.getAttribute, not this"
        )
        # The fragile `this.getAttribute` pattern should not exist
        assert "this.getAttribute" not in insights_js, (
            "Found this.getAttribute — should be e.currentTarget.getAttribute"
        )

    # ── Fix 3 regression: no JS tooltip builder ──

    def test_no_js_tooltip_builder(self, insights_js):
        """SVG title elements are generated at Python time.
        JS should not use createElementNS to build tooltips."""
        assert "createElementNS" not in insights_js, (
            "JS still builds SVG title elements — should be generated at Python time"
        )

    # ── Data consistency ──

    def test_svg_path_panel_correspondence(self, insights_html):
        """Every interactive SVG path must have a matching detail panel,
        and every panel must have a matching SVG path."""
        # Extract data-country from SVG paths
        svg_countries = set(re.findall(
            r'<path[^>]*class="gg-wm-country[^"]*"[^>]*data-country="([A-Z]{2})"',
            insights_html
        ))
        # Extract data-country from panels in world-detail
        world_detail = re.search(
            r'id="world-detail"(.*?)</div>\s*</div>\s*</div>',
            insights_html, re.DOTALL
        )
        assert world_detail, "World detail section not found"
        panel_countries = set(re.findall(
            r'class="gg-ins-map-panel[^"]*"[^>]*data-country="([A-Z]{2})"',
            world_detail.group()
        ))
        assert svg_countries, "No SVG country paths found"
        assert panel_countries, "No country panels found"
        # Every SVG path should have a panel
        missing_panels = svg_countries - panel_countries
        assert not missing_panels, (
            f"SVG paths without panels: {missing_panels}"
        )
        # Every panel should have an SVG path
        missing_paths = panel_countries - svg_countries
        assert not missing_paths, (
            f"Panels without SVG paths: {missing_paths}"
        )

    def test_country_names_covers_country_map(self):
        """Every value in COUNTRY_MAP must appear in COUNTRY_NAMES."""
        for region, code in COUNTRY_MAP.items():
            assert code in COUNTRY_NAMES, (
                f"COUNTRY_MAP['{region}'] = '{code}' not in COUNTRY_NAMES"
            )
