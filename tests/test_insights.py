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
    DIM_LABELS,
    MONTHS,
    US_STATES,
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
    extract_price,
    extract_state,
    generate_insights_page,
    load_race_index,
    safe_num,
)


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
        assert result == 150.0

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

    def test_hero_narrative(self, insights_html):
        """Hero should have narrative text with data."""
        hero_match = re.search(
            r'id="hero".*?</section>', insights_html, re.DOTALL
        )
        assert hero_match
        assert "gg-insights-narrative" in hero_match.group()


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

    # ── Geography ──
    def test_geography_section_id(self, insights_html):
        assert 'id="geography"' in insights_html

    def test_geography_title(self, insights_html):
        assert "Geography Is Destiny" in insights_html

    def test_geography_has_region_bars(self, insights_html):
        geo_match = re.search(
            r'id="geography".*?</section>', insights_html, re.DOTALL
        )
        assert geo_match
        bars = re.findall(r"gg-ins-data-bar-fill--teal", geo_match.group())
        assert len(bars) >= 3, f"Expected >=3 region bars, got {len(bars)}"

    def test_geography_avg_scores(self, insights_html):
        geo_match = re.search(
            r'id="geography".*?</section>', insights_html, re.DOTALL
        )
        assert geo_match
        assert "Avg:" in geo_match.group()

    def test_geography_data_animate(self, insights_html):
        geo_match = re.search(
            r'id="geography".*?</section>', insights_html, re.DOTALL
        )
        assert geo_match
        assert 'data-animate="bars"' in geo_match.group()

    # ── Calendar ──
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
        assert len(cards) == 4, f"Expected 4 stat cards, got {len(cards)}"

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

    def test_slider_min_0(self, insights_html):
        sliders = re.findall(r'class="gg-ins-rank-slider"[^>]*>', insights_html)
        assert len(sliders) == 6
        for s in sliders:
            assert 'min="0"' in s

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

    def test_leaderboard_present(self, insights_html):
        assert 'id="gg-ins-rank-leaderboard"' in insights_html

    def test_leaderboard_aria_live(self, insights_html):
        assert 'aria-live="polite"' in insights_html

    def test_figure_title(self, insights_html):
        assert "Your Gravel, Your Rules" in insights_html

    def test_figure_takeaway(self, insights_html):
        assert "Move the sliders" in insights_html

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
        assert "/races/" in closing_match.group()

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
        css_no_comments = re.sub(r"/\*.*?\*/", "", insights_css, flags=re.DOTALL)
        hexes = re.findall(r"#[0-9a-fA-F]{3,8}\b", css_no_comments)
        color_hexes = []
        for h in hexes:
            digits = h[1:]
            if len(digits) in (3, 4, 6, 8):
                color_hexes.append(h)
        assert len(color_hexes) == 0, f"Hardcoded hex colors found: {color_hexes[:10]}"

    def test_no_border_radius(self, insights_css):
        assert "border-radius" not in insights_css

    def test_no_box_shadow(self, insights_css):
        assert "box-shadow" not in insights_css

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
        """Explicitly confirm zero border-radius (neo-brutalist)."""
        assert insights_css.count("border-radius") == 0


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
        assert "Reset to Gravel God Defaults" in result


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
        assert "/races/" in result

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
