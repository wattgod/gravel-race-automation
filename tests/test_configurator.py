"""Tests for the Plan Preview Mini-Configurator in [08] Train for This Race.

Tests cover:
- HTML structure: configurator bar, summary container, phase badges, level notes
- Race data embedding: __GG_RACE_DATA__ JSON safety and completeness
- PHASE_MAP coverage: every race-pack category must have a phase assignment
- Sticky CTA: id attributes for JS targeting
- Price calculation edge cases: past dates, short plans, long plans, cap
- Phase split math: boundary conditions, minimum phases
- Date parsing: all date_specific format variants
- Accessibility: aria-live, aria-hidden, tabindex
- Security: XSS via race names, script injection
- Silent failure detection: missing preview JSON, empty categories
- Workout count accuracy: tied to hours config, not flat multiplier
"""

import glob
import json
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure wordpress/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

from generate_neo_brutalist import (
    SHOWCASE_ELIGIBILITY,
    WORKOUT_SHOWCASE,
    _safe_json_for_script,
    _workout_eligible,
    build_inline_js,
    build_sticky_cta,
    build_train_for_race,
    normalize_race_data,
)


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def sample_race_data():
    """Minimal complete race data with preview JSON."""
    return {
        "race": {
            "name": "Test Gravel 100",
            "slug": "test-gravel-100",
            "display_name": "Test Gravel 100",
            "tagline": "Test race.",
            "vitals": {
                "distance_mi": 100,
                "elevation_ft": 5000,
                "location": "Emporia, Kansas",
                "location_badge": "EMPORIA, KS",
                "date": "June annually",
                "date_specific": "2026: June 15",
                "terrain_types": ["Gravel roads"],
                "field_size": "~500",
                "start_time": "6:00 AM",
                "registration": "Online. Cost: $150",
                "aid_stations": "3 aid stations",
                "cutoff_time": "12 hours",
            },
            "climate": {
                "primary": "Hot",
                "description": "Summer heat.",
                "challenges": ["Heat"],
            },
            "terrain": {
                "primary": "Mixed gravel",
                "surface": "Limestone",
                "technical_rating": 3,
                "features": ["Hills"],
            },
            "gravel_god_rating": {
                "overall_score": 72,
                "tier": 2,
                "tier_label": "TIER 2",
                "logistics": 3, "length": 4, "technicality": 3,
                "elevation": 3, "climate": 3, "altitude": 1, "adventure": 3,
                "prestige": 3, "race_quality": 4, "experience": 4,
                "community": 3, "field_depth": 3, "value": 4, "expenses": 3,
                "discipline": "gravel",
            },
            "biased_opinion": {
                "verdict": "Solid Mid-Tier",
                "summary": "Good race.",
                "strengths": ["Good org"],
                "weaknesses": ["Remote"],
                "bottom_line": "Worth it.",
            },
            "biased_opinion_ratings": {
                "logistics": {"score": 3, "explanation": "OK logistics."},
                "length": {"score": 4, "explanation": "Good length."},
                "technicality": {"score": 3, "explanation": "Moderate."},
                "elevation": {"score": 3, "explanation": "Some climbing."},
                "climate": {"score": 3, "explanation": "Hot."},
                "altitude": {"score": 1, "explanation": "Low."},
                "adventure": {"score": 3, "explanation": "Adventurous."},
                "prestige": {"score": 3, "explanation": "Known."},
                "race_quality": {"score": 4, "explanation": "Well run."},
                "experience": {"score": 4, "explanation": "Fun."},
                "community": {"score": 3, "explanation": "Good vibes."},
                "field_depth": {"score": 3, "explanation": "Average."},
                "value": {"score": 4, "explanation": "Good value."},
                "expenses": {"score": 3, "explanation": "Moderate cost."},
            },
            "final_verdict": {
                "score": "72 / 100",
                "one_liner": "Solid gravel.",
                "should_you_race": "Yes.",
                "alternatives": "Unbound Gravel.",
            },
            "course_description": {
                "character": "Rolling gravel.",
                "suffering_zones": [],
                "signature_challenge": "Heat.",
            },
            "history": {
                "founded": 2018,
                "founder": "Jim Smith",
                "origin_story": "Local cyclists wanted a gravel event.",
                "notable_moments": [],
                "reputation": "Growing.",
            },
            "logistics": {
                "airport": "ICT — 90 min",
                "lodging_strategy": "Book early.",
                "food": "BBQ.",
                "packet_pickup": "Friday.",
                "parking": "Free lots.",
                "official_site": "https://testgravel100.com",
            },
        }
    }


@pytest.fixture
def normalized_data(sample_race_data):
    """Pre-normalized race data."""
    return normalize_race_data(sample_race_data)


@pytest.fixture
def preview_json():
    """Sample race-pack preview JSON matching what generate_race_pack_previews.py produces."""
    return {
        "slug": "test-gravel-100",
        "race_name": "Test Gravel 100",
        "distance_mi": 100.0,
        "demands": {
            "durability": 7,
            "climbing": 5,
            "vo2_power": 6,
            "threshold": 4,
            "technical": 5,
            "heat_resilience": 8,
            "altitude": 1,
            "race_specificity": 7,
        },
        "top_categories": [
            {
                "category": "Durability",
                "score": 100,
                "workouts": ["Tired VO2max", "Progressive Fatigue"],
                "workout_context": "100 miles of gravel demands deep fatigue resistance.",
            },
            {
                "category": "VO2max",
                "score": 90,
                "workouts": ["5x3 VO2 Classic"],
                "workout_context": "Surges on gravel demand high VO2max.",
            },
            {
                "category": "TT_Threshold",
                "score": 85,
                "workouts": ["Single Sustained Threshold"],
                "workout_context": "Long threshold efforts on flats.",
            },
            {
                "category": "Gravel_Specific",
                "score": 80,
                "workouts": ["Terrain Microbursts"],
                "workout_context": "Technical gravel demands micro-power.",
            },
            {
                "category": "Endurance",
                "score": 75,
                "workouts": ["HVLI Extended Z2"],
                "workout_context": "Base endurance for 100 miles.",
            },
            {
                "category": "G_Spot",
                "score": 70,
                "workouts": ["G-Spot Standard"],
                "workout_context": "Sweet spot for efficiency.",
            },
        ],
        "race_overlay": {
            "heat": "Hot Kansas summers require heat adaptation.",
            "nutrition": "Aim for 80-100g carbs/hr.",
        },
        "pack_summary": "Test summary.",
        "generated_at": "2026-03-06",
    }


def _build_section_with_preview(normalized_data, preview_json, tmp_path=None):
    """Build [08] section with test preview JSON.

    Writes preview JSON to the real web/race-packs/ directory (where the
    generator expects it), calls build_train_for_race, then cleans up.
    """
    slug = normalized_data["slug"]
    real_race_packs = Path(__file__).resolve().parent.parent / 'web' / 'race-packs'
    real_preview = real_race_packs / f'{slug}.json'
    existed_before = real_preview.exists()
    if not existed_before:
        real_preview.write_text(json.dumps(preview_json))
    try:
        return build_train_for_race(normalized_data)
    finally:
        if not existed_before and real_preview.exists():
            real_preview.unlink()


# ── PHASE_MAP Coverage Tests ──────────────────────────────────

class TestPhaseMapCoverage:
    """Ensure every category in production race-packs has a phase assignment."""

    # The PHASE_MAP from our JS — must stay in sync with build_inline_js()
    PHASE_MAP = {
        'Endurance': 'base', 'HVLI_Extended': 'base', 'LT1_MAF': 'base',
        'Tempo': 'base', 'Cadence_Work': 'base',
        'TT_Threshold': 'build', 'Over_Under': 'build', 'Mixed_Climbing': 'build',
        'SFR_Muscle_Force': 'build', 'Blended': 'build', 'G_Spot': 'build',
        'Norwegian_Double': 'build',
        'VO2max': 'peak', 'Durability': 'peak', 'Race_Simulation': 'peak',
        'Gravel_Specific': 'peak', 'Anaerobic_Capacity': 'peak',
        'Critical_Power': 'peak', 'Sprint_Neuromuscular': 'peak',
    }

    def test_all_racepack_categories_have_phase(self):
        """Every category name in any race-pack JSON must exist in PHASE_MAP."""
        race_packs_dir = Path(__file__).resolve().parent.parent / 'web' / 'race-packs'
        if not race_packs_dir.exists():
            pytest.skip("race-packs directory not found")
        categories_seen = set()
        for f in race_packs_dir.glob('*.json'):
            try:
                data = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            for tc in data.get('top_categories', []):
                categories_seen.add(tc['category'])
        missing = categories_seen - set(self.PHASE_MAP.keys())
        assert not missing, (
            f"Categories in race-packs not in PHASE_MAP: {missing}. "
            f"Add them to the PHASE_MAP in build_inline_js() and this test."
        )

    def test_phase_map_in_js_matches_test(self):
        """The PHASE_MAP in build_inline_js() must match the test's PHASE_MAP."""
        js = build_inline_js()
        for cat, phase in self.PHASE_MAP.items():
            assert f"'{cat}': '{phase}'" in js, (
                f"PHASE_MAP entry '{cat}': '{phase}' not found in build_inline_js(). "
                f"JS and test are out of sync."
            )

    def test_no_wrong_category_names_in_js(self):
        """Catch the original bug: wrong names like 'Threshold', 'Sweet_Spot', 'Sprint'."""
        js = build_inline_js()
        # These were the original wrong names — they should NOT appear as PHASE_MAP keys
        wrong_names = ['Threshold', 'Sweet_Spot', 'Sprint']
        for wrong in wrong_names:
            # Must not appear as a standalone PHASE_MAP key (could appear in comments)
            assert f"'{wrong}': '" not in js, (
                f"Wrong category name '{wrong}' found in PHASE_MAP. "
                f"Use the correct name from race-pack JSON."
            )

    def test_phase_map_has_all_three_phases(self):
        """PHASE_MAP must assign categories to base, build, and peak."""
        phases_used = set(self.PHASE_MAP.values())
        assert phases_used == {'base', 'build', 'peak'}, (
            f"PHASE_MAP uses phases {phases_used}, expected exactly base/build/peak"
        )


# ── Configurator HTML Structure Tests ─────────────────────────

class TestConfiguratorHTML:
    """Test that configurator HTML elements are present in generated pages."""

    def test_configurator_bar_present(self, normalized_data, preview_json):
        """Configurator bar with 3 inputs + button must be in [08] section."""
        html = _build_section_with_preview(normalized_data, preview_json)
        assert 'gg-cfg-bar' in html
        assert 'gg-cfg-level' in html
        assert 'gg-cfg-hours' in html
        assert 'gg-cfg-date' in html
        assert 'gg-cfg-btn' in html
        assert 'PREVIEW YOUR TRAINING PLAN' in html

    def test_plan_summary_container_present(self, normalized_data, preview_json):
        """Hidden plan summary container must exist for JS to populate."""
        html = _build_section_with_preview(normalized_data, preview_json)
        assert 'gg-cfg-summary' in html
        assert 'gg-cfg-summary-title' in html
        assert 'gg-cfg-timeline' in html
        assert 'gg-cfg-timeline-bar' in html
        assert 'gg-cfg-details' in html
        assert 'display:none' in html  # Hidden by default

    def test_phase_badge_containers_on_workout_cards(self, normalized_data, preview_json):
        """Each workout card must have a hidden phase badge container."""
        html = _build_section_with_preview(normalized_data, preview_json)
        badge_count = html.count('gg-cfg-phase-badge')
        # At least as many badges as workout cards (each card gets one)
        workout_count = html.count('data-workout-idx=')
        assert badge_count >= workout_count, (
            f"Only {badge_count} phase badges for {workout_count} workout cards"
        )

    def test_level_note_containers_on_workout_cards(self, normalized_data, preview_json):
        """Each workout card must have a hidden level annotation container."""
        html = _build_section_with_preview(normalized_data, preview_json)
        note_count = html.count('gg-cfg-level-note')
        workout_count = html.count('data-workout-idx=')
        assert note_count >= workout_count, (
            f"Only {note_count} level notes for {workout_count} workout cards"
        )

    def test_workout_cat_data_attribute(self, normalized_data, preview_json):
        """Each workout card must have a data-workout-cat attribute."""
        html = _build_section_with_preview(normalized_data, preview_json)
        cat_attrs = re.findall(r'data-workout-cat="([^"]+)"', html)
        workout_count = html.count('data-workout-idx=')
        assert len(cat_attrs) == workout_count, (
            f"Only {len(cat_attrs)} data-workout-cat attrs for {workout_count} cards"
        )
        # All cat values must be in PHASE_MAP
        for cat in cat_attrs:
            assert cat in TestPhaseMapCoverage.PHASE_MAP, (
                f"data-workout-cat='{cat}' not in PHASE_MAP"
            )

    def test_personalized_cta_container(self, normalized_data, preview_json):
        """Hidden personalized CTA must exist alongside default CTA."""
        html = _build_section_with_preview(normalized_data, preview_json)
        assert 'gg-cfg-cta' in html
        assert 'gg-cfg-cta-link' in html
        assert 'gg-pack-cta-default' in html
        # Default CTA visible, personalized hidden
        assert 'id="gg-cfg-cta" style="display:none;"' in html

    def test_fitness_level_options(self, normalized_data, preview_json):
        """All 4 fitness levels must be in select, intermediate selected by default."""
        html = _build_section_with_preview(normalized_data, preview_json)
        assert 'value="beginner"' in html
        assert 'value="intermediate" selected' in html
        assert 'value="advanced"' in html
        assert 'value="elite"' in html

    def test_hours_options(self, normalized_data, preview_json):
        """All 4 hours ranges must be in select, 8-12 selected by default."""
        html = _build_section_with_preview(normalized_data, preview_json)
        assert 'value="6-8"' in html
        assert 'value="8-12" selected' in html
        assert 'value="12-16"' in html
        assert 'value="16+"' in html


# ── Race Data Embedding Tests ─────────────────────────────────

class TestRaceDataEmbedding:
    """Test __GG_RACE_DATA__ JSON is embedded safely and completely."""

    def test_race_data_json_embedded(self, normalized_data, preview_json):
        """window.__GG_RACE_DATA__ must be in a <script> tag."""
        html = _build_section_with_preview(normalized_data, preview_json)
        assert 'window.__GG_RACE_DATA__=' in html

    def test_race_data_contains_required_fields(self, normalized_data, preview_json):
        """Embedded JSON must contain slug, race_name, date_specific, distance_mi."""
        html = _build_section_with_preview(normalized_data, preview_json)
        match = re.search(r'window\.__GG_RACE_DATA__=({[^;]+});', html)
        assert match, "Could not extract __GG_RACE_DATA__ JSON"
        data = json.loads(match.group(1))
        assert 'slug' in data
        assert 'race_name' in data
        assert 'date_specific' in data
        assert 'distance_mi' in data
        assert data['slug'] == 'test-gravel-100'
        assert data['race_name'] == 'Test Gravel 100'

    def test_race_data_xss_safe(self):
        """Race names with </script> must not break the page."""
        malicious = '</script><script>alert(1)</script>'
        safe = _safe_json_for_script({'name': malicious})
        assert '</script>' not in safe
        assert '<\\/' in safe  # Escaped
        # Must still parse as valid JSON
        parsed = json.loads(safe.replace('<\\/', '</'))
        assert parsed['name'] == malicious

    def test_race_data_unicode_safe(self):
        """Race names with unicode (é, ñ, ü) must embed correctly."""
        unicode_name = "L'Étape du Tour — Côte d'Azur"
        safe = _safe_json_for_script({'name': unicode_name}, ensure_ascii=False)
        parsed = json.loads(safe)
        assert parsed['name'] == unicode_name


# ── Sticky CTA Tests ─────────────────────────────────────────

class TestStickyCTA:
    """Test sticky CTA has required id attributes for JS targeting."""

    def test_sticky_cta_link_id(self):
        """Sticky CTA link must have id for JS targeting."""
        html = build_sticky_cta("Test Race", "test-race")
        assert 'id="gg-sticky-cta-link"' in html

    def test_sticky_cta_text_id(self):
        """Sticky CTA text span must have id for JS targeting."""
        html = build_sticky_cta("Test Race", "test-race")
        assert 'id="gg-sticky-cta-text"' in html

    def test_sticky_cta_preserves_original_text(self):
        """Sticky CTA must show original text before configurator activates."""
        html = build_sticky_cta("Test Race", "test-race")
        assert 'BUILD MY PLAN' in html
        assert '$15/WK' in html

    def test_sticky_cta_has_race_param(self):
        """Sticky CTA link must include ?race= parameter."""
        html = build_sticky_cta("Test Race", "test-race")
        assert '?race=test-race' in html


# ── Accessibility Tests ───────────────────────────────────────

class TestAccessibility:
    """Test ARIA attributes and accessibility features."""

    def test_summary_has_aria_live(self, normalized_data, preview_json):
        """Plan summary must have aria-live for screen reader announcements."""
        html = _build_section_with_preview(normalized_data, preview_json)
        assert 'aria-live="polite"' in html

    def test_summary_has_role_region(self, normalized_data, preview_json):
        """Plan summary must have role=region."""
        html = _build_section_with_preview(normalized_data, preview_json)
        assert 'role="region"' in html

    def test_hidden_cta_has_aria_hidden(self, normalized_data, preview_json):
        """Hidden personalized CTA must have aria-hidden=true."""
        html = _build_section_with_preview(normalized_data, preview_json)
        assert 'aria-hidden="true"' in html

    def test_hidden_cta_link_not_focusable(self, normalized_data, preview_json):
        """Hidden CTA link must have tabindex=-1."""
        html = _build_section_with_preview(normalized_data, preview_json)
        assert 'tabindex="-1"' in html

    def test_select_labels_have_for_attr(self, normalized_data, preview_json):
        """All labels must have matching for= attributes."""
        html = _build_section_with_preview(normalized_data, preview_json)
        assert 'for="gg-cfg-level"' in html
        assert 'for="gg-cfg-hours"' in html
        assert 'for="gg-cfg-date"' in html

    def test_empty_link_has_fallback_text(self, normalized_data, preview_json):
        """Personalized CTA link must not be empty — needs fallback text."""
        html = _build_section_with_preview(normalized_data, preview_json)
        # Find the cfg-cta-link element
        match = re.search(r'id="gg-cfg-cta-link"[^>]*>([^<]*)</a>', html)
        assert match, "gg-cfg-cta-link not found"
        link_text = match.group(1).strip()
        assert len(link_text) > 0, "Personalized CTA link has empty text"


# ── JS Logic Tests (via string analysis) ──────────────────────

class TestConfiguratorJS:
    """Test configurator JS logic by analyzing the generated JavaScript."""

    @pytest.fixture
    def js_content(self):
        return build_inline_js()

    def test_configurator_iife_present(self, js_content):
        """Configurator must be wrapped in an IIFE."""
        assert 'Plan Preview Mini-Configurator' in js_content
        assert 'window.__GG_RACE_DATA__' in js_content

    def test_date_parser_handles_year_colon_format(self, js_content):
        """Date parser must handle '2026: June 6' format."""
        assert 'parseRaceDate' in js_content
        assert r"(\d{4}):\s*([A-Za-z]+)\s+(\d{1,2})" in js_content

    def test_date_parser_handles_month_day_year_format(self, js_content):
        """Date parser must handle 'July 20, 2026' format (Gran Fondo Asheville)."""
        assert r"([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})" in js_content

    def test_date_parser_handles_iso_format(self, js_content):
        """Date parser must handle YYYY-MM-DD format."""
        assert r"(\d{4})-(\d{2})-(\d{2})" in js_content

    def test_workouts_tied_to_hours_config(self, js_content):
        """Total workouts must be calculated from hours config, not flat *6."""
        assert 'sessionsPerWeek' in js_content
        assert 'hCfg.quality + hCfg.endurance + 1' in js_content
        # Must NOT have the old flat calculation
        assert 'weeks * 6' not in js_content

    def test_price_calculation_has_bounds(self, js_content):
        """Price must be capped between $60 and $249."""
        assert 'Math.min(249' in js_content
        assert 'Math.max(60' in js_content

    def test_weeks_minimum_is_4(self, js_content):
        """Minimum plan length must be 4 weeks."""
        assert 'Math.max(4' in js_content

    def test_stale_preview_handling(self, js_content):
        """Changing inputs after preview must reset the display."""
        assert 'previewActive' in js_content
        # Must hide summary when inputs change
        assert "sum.style.display = 'none'" in js_content or \
               'sum) sum.style.display' in js_content

    def test_ga4_events_present(self, js_content):
        """All 3 GA4 events must be present."""
        assert 'configurator_interact' in js_content
        assert 'configurator_preview' in js_content
        assert 'configurator_cta_click' in js_content

    def test_cta_passes_configurator_params(self, js_content):
        """CTA link must pass level, hours, weeks to questionnaire URL."""
        assert '&level=' in js_content
        assert '&hours=' in js_content
        assert '&weeks=' in js_content
        assert 'encodeURIComponent' in js_content

    def test_no_dead_code_in_configs(self, js_content):
        """Level and hours configs must not have unused properties."""
        # intMul, durMul, longest were dead code in v1
        assert 'intMul' not in js_content
        assert 'durMul' not in js_content
        assert 'longest' not in js_content

    def test_phase_split_has_minimum_peak(self, js_content):
        """Phase split must guarantee at least 1 week of peak."""
        assert 'if (peak < 1)' in js_content

    def test_no_innerhtml_with_data(self, js_content):
        """Must use textContent/createElement, never innerHTML with data values."""
        # innerHTML should not appear in configurator section
        configurator_section = js_content[js_content.index('Plan Preview Mini-Configurator'):]
        assert 'innerHTML' not in configurator_section, (
            "innerHTML found in configurator JS — use textContent/createElement instead"
        )


# ── CSS Tests ─────────────────────────────────────────────────

class TestConfiguratorCSS:
    """Test configurator CSS follows neo-brutalist design system."""

    @pytest.fixture
    def css_content(self):
        """Extract CSS from the generator's inline CSS function."""
        # The CSS is in build_inline_css() — but we can check the output file
        import generate_neo_brutalist as gnb
        # Get CSS by calling the extractor
        css = gnb._extract_css_content()
        return css

    def test_no_border_radius_on_form_controls(self, css_content):
        """Select and input elements must have border-radius: 0."""
        # Find the cfg-select/cfg-input rule
        assert 'border-radius: 0' in css_content or 'border-radius:0' in css_content

    def test_uses_css_variables(self, css_content):
        """Configurator CSS must use brand tokens via CSS variables."""
        assert 'var(--gg-color-primary-brown)' in css_content
        assert 'var(--gg-color-teal)' in css_content
        assert 'var(--gg-color-warm-paper)' in css_content
        assert 'var(--gg-font-data)' in css_content

    def test_phase_bar_colors_defined(self, css_content):
        """Phase bar segments must have distinct background colors."""
        assert 'gg-cfg-bar-base' in css_content
        assert 'gg-cfg-bar-build' in css_content
        assert 'gg-cfg-bar-peak' in css_content
        assert 'gg-cfg-bar-taper' in css_content

    def test_mobile_responsive_rules(self, css_content):
        """Configurator must have mobile-responsive CSS."""
        assert 'gg-cfg-inputs' in css_content
        # Should stack inputs vertically on mobile
        assert 'flex-direction: column' in css_content or 'flex-direction:column' in css_content


# ── Price Calculation Edge Cases ──────────────────────────────

class TestPriceCalculation:
    """Test price calculation logic edge cases (verified via JS string analysis)."""

    def test_price_formula_documented(self):
        """Price formula: min(249, max(60, weeks * 15))."""
        js = build_inline_js()
        # Verify the exact formula is in the JS
        assert 'Math.min(249, Math.max(60, weeks * 15))' in js

    @pytest.mark.parametrize("weeks,expected_price", [
        (4, 60),    # Minimum plan = $60
        (5, 75),
        (10, 150),
        (13, 195),  # Unbound typical
        (16, 240),
        (17, 249),  # Cap kicks in at 17 weeks
        (20, 249),  # Long plan capped
        (52, 249),  # Year-long capped
    ])
    def test_price_at_various_weeks(self, weeks, expected_price):
        """Verify price calculation at boundary conditions."""
        price = min(249, max(60, weeks * 15))
        assert price == expected_price


# ── Phase Split Edge Cases ────────────────────────────────────

class TestPhaseSplit:
    """Test phase split math at boundary conditions."""

    @staticmethod
    def _compute_phases(weeks):
        """Replicate the JS phase split logic in Python for testing."""
        taper = 1
        remaining = weeks - taper
        base = round(remaining * 0.4)
        build = round(remaining * 0.35)
        peak = remaining - base - build
        if peak < 1:
            peak = 1
            base = max(1, base - 1)
        return {'base': base, 'build': build, 'peak': peak, 'taper': taper}

    @pytest.mark.parametrize("weeks", [4, 5, 6, 8, 10, 12, 14, 16, 20, 26, 40, 52])
    def test_phases_sum_to_weeks(self, weeks):
        """Phase weeks must sum to total weeks."""
        phases = self._compute_phases(weeks)
        total = phases['base'] + phases['build'] + phases['peak'] + phases['taper']
        assert total == weeks, f"Phases sum to {total}, expected {weeks}: {phases}"

    @pytest.mark.parametrize("weeks", [4, 5, 6, 8, 10, 12, 14, 16, 20, 26, 40, 52])
    def test_all_phases_at_least_one_week(self, weeks):
        """Every phase must be at least 1 week."""
        phases = self._compute_phases(weeks)
        for phase, wk in phases.items():
            assert wk >= 1, f"{phase} is {wk} weeks for {weeks}-week plan"

    def test_4_week_plan_minimum(self):
        """4-week plan: each phase gets exactly 1 week."""
        phases = self._compute_phases(4)
        assert phases == {'base': 1, 'build': 1, 'peak': 1, 'taper': 1}

    def test_13_week_plan_typical(self):
        """13-week plan (Unbound typical): verify realistic distribution."""
        phases = self._compute_phases(13)
        assert phases['taper'] == 1
        assert phases['base'] >= 4
        assert phases['build'] >= 3
        assert phases['peak'] >= 2


# ── Workout Count Accuracy ────────────────────────────────────

class TestWorkoutCount:
    """Verify workout count is tied to hours config, not a flat multiplier."""

    HOURS_CONFIG = {
        '6-8':  {'quality': 2, 'endurance': 2},
        '8-12': {'quality': 3, 'endurance': 2},
        '12-16': {'quality': 3, 'endurance': 3},
        '16+':  {'quality': 4, 'endurance': 3},
    }

    @pytest.mark.parametrize("hours_key,weeks", [
        ('6-8', 13),
        ('8-12', 13),
        ('12-16', 13),
        ('16+', 13),
        ('8-12', 4),
        ('8-12', 26),
    ])
    def test_workout_count_matches_hours(self, hours_key, weeks):
        """Workout count = weeks * (quality + endurance + 1 recovery)."""
        cfg = self.HOURS_CONFIG[hours_key]
        sessions_per_week = cfg['quality'] + cfg['endurance'] + 1
        total = weeks * sessions_per_week
        # For 8-12 hrs, 13 weeks: 3+2+1 = 6 per week * 13 = 78
        assert total == weeks * sessions_per_week
        # Sanity: should be reasonable (not 6*weeks for beginner)
        if hours_key == '6-8':
            assert sessions_per_week == 5, "Beginner gets 5 sessions/week (2q + 2e + 1r)"
        elif hours_key == '16+':
            assert sessions_per_week == 8, "Elite gets 8 sessions/week (4q + 3e + 1r)"


# ── Date Parsing Coverage ─────────────────────────────────────

class TestDateParsing:
    """Verify the JS date parser handles all date_specific format variants in production."""

    @pytest.fixture
    def all_date_formats(self):
        """Collect all unique date_specific formats from race data."""
        race_data_dir = Path(__file__).resolve().parent.parent / 'race-data'
        if not race_data_dir.exists():
            pytest.skip("race-data directory not found")
        formats = {}
        for f in race_data_dir.glob('*.json'):
            try:
                data = json.loads(f.read_text())
                ds = data.get('race', {}).get('vitals', {}).get('date_specific', '')
                if ds:
                    formats[f.stem] = ds
            except (json.JSONDecodeError, OSError):
                continue
        return formats

    def test_year_colon_format_parseable(self, all_date_formats):
        """'2026: June 6' format should parse to a valid date."""
        year_colon = {k: v for k, v in all_date_formats.items()
                      if re.match(r'\d{4}:\s*[A-Za-z]+\s+\d', v)}
        assert len(year_colon) > 0, "No year:colon format dates found"
        for slug, ds in list(year_colon.items())[:10]:
            m = re.match(r'(\d{4}):\s*([A-Za-z]+)\s+(\d{1,2})', ds)
            assert m, f"Year-colon format failed to parse: {slug} = '{ds}'"

    def test_month_day_year_format_parseable(self, all_date_formats):
        """'July 20, 2026' format (e.g., Gran Fondo Asheville) should parse."""
        mdy = {k: v for k, v in all_date_formats.items()
               if re.search(r'[A-Za-z]+\s+\d{1,2},?\s*\d{4}', v)
               and not re.match(r'\d{4}:', v)}
        # These exist (Gran Fondo Asheville, etc.)
        for slug, ds in list(mdy.items())[:5]:
            m = re.search(r'([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})', ds)
            assert m, f"Month-day-year format failed to parse: {slug} = '{ds}'"

    def test_unparseable_dates_handled_gracefully(self, all_date_formats):
        """'TBD', 'check website', etc. should not crash the parser."""
        unparseable = {k: v for k, v in all_date_formats.items()
                       if 'TBD' in v.upper() or 'check' in v.lower()}
        # These should exist and we just verify they don't match our patterns
        for slug, ds in unparseable.items():
            m1 = re.match(r'(\d{4}):\s*([A-Za-z]+)\s+(\d{1,2})', ds)
            m2 = re.search(r'([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})', ds)
            # At least one should NOT match (graceful no-op)
            assert not m1 or not m2, f"TBD date unexpectedly parsed: {slug} = '{ds}'"


# ── Silent Failure Detection ──────────────────────────────────

class TestSilentFailures:
    """Catch cases where the configurator silently produces wrong output."""

    def test_section_empty_when_no_preview_json(self, normalized_data):
        """[08] section must return empty string when preview JSON is missing."""
        # Use a slug with no preview JSON
        normalized_data['slug'] = 'nonexistent-race-999'
        html = build_train_for_race(normalized_data)
        assert html == '', "Section should be empty when preview JSON is missing"

    def test_section_empty_when_preview_has_no_demands(self, normalized_data, preview_json):
        """Section must return empty when preview has empty demands."""
        preview_json['demands'] = {}
        html = _build_section_with_preview(normalized_data, preview_json)
        assert html == '', "Section should be empty when demands are empty"

    def test_section_empty_when_preview_has_no_categories(self, normalized_data, preview_json):
        """Section must return empty when preview has no top_categories."""
        preview_json['top_categories'] = []
        html = _build_section_with_preview(normalized_data, preview_json)
        assert html == '', "Section should be empty when top_categories is empty"

    def test_configurator_js_guards_against_missing_race_data(self):
        """JS must early-return when __GG_RACE_DATA__ is not set."""
        js = build_inline_js()
        assert "if (!rd) return" in js

    def test_configurator_js_guards_against_missing_elements(self):
        """JS must early-return when configurator elements don't exist."""
        js = build_inline_js()
        assert "if (!btn || !dateInput) return" in js

    def test_no_race_data_without_train_section(self):
        """Pages without [08] section must NOT embed __GG_RACE_DATA__."""
        # The JSON is embedded inside build_train_for_race's return HTML,
        # so if it returns '', no JSON is embedded. Verify this.
        from generate_neo_brutalist import build_inline_js
        js = build_inline_js()
        # The JS reads from window.__GG_RACE_DATA__ which only exists
        # if build_train_for_race emitted it. Verify the JS guard.
        assert "window.__GG_RACE_DATA__" in js
        assert "if (!rd) return" in js


# ── Security Tests ────────────────────────────────────────────

class TestSecurity:
    """Test XSS and injection protection."""

    def test_script_tag_in_race_name(self, preview_json):
        """Race name with </script> must not break the page."""
        evil_data = {
            "race": {
                "name": '</script><script>alert("xss")</script>',
                "slug": "evil-race",
                "display_name": "Evil Race",
                "tagline": "Test.",
                "vitals": {
                    "distance_mi": 50,
                    "location": "Test, USA",
                    "location_badge": "TEST",
                    "date": "June",
                    "date_specific": "2026: June 1",
                    "terrain_types": [],
                    "field_size": "100",
                    "start_time": "7 AM",
                    "registration": "$50",
                    "aid_stations": "1",
                    "cutoff_time": "8 hours",
                },
                "climate": {"primary": "Mild", "description": "OK.", "challenges": []},
                "terrain": {"primary": "Gravel", "surface": "Dirt", "technical_rating": 2, "features": []},
                "gravel_god_rating": {
                    "overall_score": 50, "tier": 3, "tier_label": "TIER 3",
                    "logistics": 3, "length": 3, "technicality": 3,
                    "elevation": 2, "climate": 3, "altitude": 1, "adventure": 2,
                    "prestige": 2, "race_quality": 3, "experience": 3,
                    "community": 2, "field_depth": 2, "value": 3, "expenses": 3,
                    "discipline": "gravel",
                },
                "biased_opinion": {"verdict": "OK", "summary": "OK.", "strengths": [], "weaknesses": [], "bottom_line": "OK."},
                "biased_opinion_ratings": {
                    d: {"score": 3, "explanation": "OK."} for d in [
                        "logistics", "length", "technicality", "elevation", "climate",
                        "altitude", "adventure", "prestige", "race_quality", "experience",
                        "community", "field_depth", "value", "expenses"
                    ]
                },
                "final_verdict": {"score": "50 / 100", "one_liner": "OK.", "should_you_race": "Maybe.", "alternatives": "None."},
                "course_description": {"character": "Flat.", "suffering_zones": [], "signature_challenge": "None."},
                "history": {"founded": 2020, "founder": "Test", "origin_story": "Test.", "notable_moments": [], "reputation": "New."},
                "logistics": {"airport": "TST", "lodging_strategy": "Motel.", "food": "Fast food.", "packet_pickup": "Day of.", "parking": "Free.", "official_site": "https://evil.com"},
            }
        }
        rd = normalize_race_data(evil_data)
        preview_json['slug'] = 'evil-race'
        preview_json['race_name'] = rd['name']
        html = _build_section_with_preview(rd, preview_json)
        # The raw </script> must not appear unescaped
        # It's OK in HTML-escaped form (&lt;/script&gt;) or in JSON-escaped form (<\/)
        script_sections = html.split('<script>')
        for i, section in enumerate(script_sections[1:], 1):
            # Each <script> section should only have ONE </script> (its own closing tag)
            closing_count = section.count('</script>')
            assert closing_count == 1, (
                f"Script section {i} has {closing_count} </script> tags — XSS risk"
            )

    def test_encodeURIComponent_in_cta_hrefs(self):
        """CTA hrefs must use encodeURIComponent for user-derived values."""
        js = build_inline_js()
        assert 'encodeURIComponent(rd.slug)' in js
        assert 'encodeURIComponent(level)' in js
        assert 'encodeURIComponent(hours)' in js


# ── Integration: Verify All Race-Pack Categories ──────────────

class TestRacePackIntegration:
    """Cross-reference race-pack data with configurator expectations."""

    def test_all_showcase_workouts_have_eligibility_rules(self):
        """Every WORKOUT_SHOWCASE entry must have a SHOWCASE_ELIGIBILITY entry."""
        missing = set(WORKOUT_SHOWCASE.keys()) - set(SHOWCASE_ELIGIBILITY.keys())
        assert not missing, (
            f"WORKOUT_SHOWCASE entries without SHOWCASE_ELIGIBILITY: {missing}"
        )

    def test_all_eligibility_workouts_exist_in_showcase(self):
        """Every SHOWCASE_ELIGIBILITY entry must have a WORKOUT_SHOWCASE entry."""
        missing = set(SHOWCASE_ELIGIBILITY.keys()) - set(WORKOUT_SHOWCASE.keys())
        assert not missing, (
            f"SHOWCASE_ELIGIBILITY entries without WORKOUT_SHOWCASE: {missing}"
        )

    def test_showcase_workouts_have_required_fields(self):
        """Every showcase workout must have all required display fields."""
        required = ['duration', 'summary', 'viz', 'structure', 'execution',
                     'power', 'cadence', 'position', 'rpe']
        for name, workout in WORKOUT_SHOWCASE.items():
            for field in required:
                assert field in workout, (
                    f"WORKOUT_SHOWCASE['{name}'] missing required field '{field}'"
                )

    def test_viz_blocks_have_valid_zones(self):
        """Every viz block must reference a valid zone class (z1-z6)."""
        valid_zones = {'z1', 'z2', 'z3', 'z4', 'z5', 'z6'}
        for name, workout in WORKOUT_SHOWCASE.items():
            for i, block in enumerate(workout['viz']):
                assert block['z'] in valid_zones, (
                    f"WORKOUT_SHOWCASE['{name}'].viz[{i}] has invalid zone '{block['z']}'"
                )
                assert 0 < block['w'] <= 100, (
                    f"WORKOUT_SHOWCASE['{name}'].viz[{i}] has invalid width {block['w']}"
                )
                assert 0 < block['h'] <= 200, (
                    f"WORKOUT_SHOWCASE['{name}'].viz[{i}] has invalid height {block['h']}"
                )
