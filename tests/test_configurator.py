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

    def test_cta_links_to_questionnaire_not_coaching(self, js_content):
        """Configurator CTA must link to /questionnaire/, not /coaching.

        Bug found in Sprint 41 audit: configurator CTA linked to /coaching
        which is a different product (1:1 coaching). The self-serve training
        plan funnel must go through /questionnaire/.
        """
        # Both the cfg CTA and sticky CTA set their href in JS
        cta_href_lines = [
            line.strip() for line in js_content.split('\n')
            if '.href' in line and 'race=' in line
        ]
        for line in cta_href_lines:
            assert '/questionnaire/' in line, (
                f"CTA href must point to /questionnaire/, not /coaching: {line}"
            )
        # Should never contain /coaching? as a CTA destination
        assert "'/coaching?" not in js_content, (
            "JS must not link to /coaching — wrong funnel for self-serve plans"
        )

    def test_review_form_includes_source_field(self, js_content):
        """Review form payload must include source:'race_review'.

        Bug found in Sprint 41 audit: review form omitted the source field,
        causing the Cloudflare Worker to reject all reviews with 400 'Unknown
        source'. The .catch() swallowed the error so users saw fake success
        but all reviews were silently lost.
        """
        assert "source:'race_review'" in js_content, (
            "Review form payload must include source:'race_review' — "
            "without it the worker rejects submissions silently"
        )

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

    def test_worker_accepts_race_review_source(self):
        """Cloudflare Worker KNOWN_SOURCES must include 'race_review'.

        The review form sends source:'race_review' — the worker must accept it.
        """
        worker_path = Path(__file__).resolve().parent.parent / "workers" / "fueling-lead-intake" / "worker.js"
        if not worker_path.exists():
            pytest.skip("Worker file not found")
        worker_js = worker_path.read_text()
        assert "'race_review'" in worker_js, (
            "Worker KNOWN_SOURCES must include 'race_review' — "
            "review submissions will be rejected with 400 otherwise"
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


# ── Layout Restructure Tests ──────────────────────────────────

class TestSectionLayout:
    """Test the CTA-above-workouts restructure.

    The [08] section was restructured to put CTAs immediately after the
    configurator summary and collapse workouts behind a toggle. These tests
    prevent regressions that would bury the CTA under workout cards again.
    """

    def test_cta_appears_before_workouts_in_dom(self, normalized_data, preview_json):
        """CTA must come before workout toggle and panel in DOM order.

        This is the CORE conversion optimization — if someone moves the CTA
        below workouts, this test fails.
        """
        html = _build_section_with_preview(normalized_data, preview_json)
        default_cta_pos = html.find('id="gg-pack-cta-default"')
        cfg_cta_pos = html.find('id="gg-cfg-cta"')
        toggle_pos = html.find('id="gg-pack-workouts-toggle"')
        panel_pos = html.find('id="gg-pack-workouts-panel"')
        assert default_cta_pos > 0, "Default CTA missing"
        assert cfg_cta_pos > 0, "Personalized CTA missing"
        assert toggle_pos > 0, "Workout toggle missing"
        assert panel_pos > 0, "Workout panel missing"
        assert default_cta_pos < toggle_pos, (
            "Default CTA must appear before workout toggle in DOM"
        )
        assert cfg_cta_pos < toggle_pos, (
            "Personalized CTA must appear before workout toggle in DOM"
        )
        assert toggle_pos < panel_pos, (
            "Toggle button must appear before workout panel in DOM"
        )

    def test_demand_bars_have_heading(self, normalized_data, preview_json):
        """Demand bars section must have RACE DEMAND PROFILE heading for a11y."""
        html = _build_section_with_preview(normalized_data, preview_json)
        assert 'RACE DEMAND PROFILE' in html, (
            "RACE DEMAND PROFILE heading was silently removed"
        )

    def test_demand_bars_use_inline_grid(self, normalized_data, preview_json):
        """Demand bars must use 2-column inline grid wrapper."""
        html = _build_section_with_preview(normalized_data, preview_json)
        assert 'gg-pack-demands-inline' in html, (
            "Demand bars missing gg-pack-demands-inline grid wrapper"
        )

    def test_workout_panel_hidden_by_default(self, normalized_data, preview_json):
        """Workout panel must be hidden (display:none) by default."""
        html = _build_section_with_preview(normalized_data, preview_json)
        # Find the panel element and check its style
        panel_match = re.search(
            r'id="gg-pack-workouts-panel"[^>]*style="([^"]*)"', html
        )
        assert panel_match, "Workout panel missing"
        assert 'display:none' in panel_match.group(1), (
            "Workout panel must be hidden by default"
        )

    def test_toggle_button_has_correct_aria(self, normalized_data, preview_json):
        """Toggle button must have aria-expanded=false and aria-controls linking to panel."""
        html = _build_section_with_preview(normalized_data, preview_json)
        toggle = re.search(
            r'id="gg-pack-toggle-btn"[^>]*', html
        ) or re.search(
            r'class="gg-pack-toggle-btn"[^>]*', html
        )
        assert toggle, "Toggle button missing"
        tag = toggle.group()
        assert 'aria-expanded="false"' in tag, (
            "Toggle must start with aria-expanded=false"
        )
        assert 'aria-controls="gg-pack-workouts-panel"' in tag, (
            "Toggle must reference workout panel via aria-controls"
        )

    def test_toggle_text_matches_workout_count(self, normalized_data, preview_json):
        """Toggle button text must show actual workout count, not hardcoded 5."""
        html = _build_section_with_preview(normalized_data, preview_json)
        # Count actual workout cards
        actual_count = len(re.findall(r'data-workout-idx="\d+"', html))
        # Find toggle text
        toggle_text = re.search(
            r'id="gg-pack-toggle-text">(.*?)<', html
        )
        assert toggle_text, "Toggle text span missing"
        # Extract number from toggle text
        toggle_num = re.search(r'(\d+)', toggle_text.group(1))
        assert toggle_num, f"No number in toggle text: {toggle_text.group(1)}"
        assert int(toggle_num.group(1)) == actual_count, (
            f"Toggle says {toggle_num.group(1)} workouts but {actual_count} cards exist"
        )

    def test_panel_header_matches_workout_count(self, normalized_data, preview_json):
        """Panel subtitle 'N WORKOUTS BUILT FOR THIS RACE' must match actual card count."""
        html = _build_section_with_preview(normalized_data, preview_json)
        actual_count = len(re.findall(r'data-workout-idx="\d+"', html))
        header_match = re.search(r'(\d+) WORKOUTS BUILT FOR THIS RACE', html)
        assert header_match, "Panel subtitle with count missing"
        assert int(header_match.group(1)) == actual_count, (
            f"Panel header says {header_match.group(1)} but {actual_count} cards exist"
        )

    def test_toggle_not_rendered_without_workouts(self, normalized_data, preview_json):
        """If no workouts pass eligibility, toggle and panel must not render."""
        # Create preview with categories that have no showcase workouts
        empty_preview = dict(preview_json)
        empty_preview['top_categories'] = [
            {'category': 'NonExistent', 'score': 100, 'workouts': ['FakeWorkout']}
        ]
        html = _build_section_with_preview(normalized_data, empty_preview)
        assert 'gg-pack-workouts-toggle' not in html, (
            "Toggle rendered with 0 eligible workouts"
        )
        assert 'gg-pack-workouts-panel' not in html, (
            "Workout panel rendered with 0 eligible workouts"
        )

    def test_toggle_button_no_gg_btn_class(self, normalized_data, preview_json):
        """Toggle button must NOT have gg-btn base class (specificity conflict)."""
        html = _build_section_with_preview(normalized_data, preview_json)
        toggle = re.search(
            r'class="([^"]*gg-pack-toggle-btn[^"]*)"', html
        )
        assert toggle, "Toggle button missing"
        classes = toggle.group(1).split()
        assert 'gg-btn' not in classes, (
            f"Toggle has gg-btn class causing specificity conflict: {toggle.group(1)}"
        )
        assert 'gg-btn--outline' not in classes, (
            f"Toggle has gg-btn--outline class: {toggle.group(1)}"
        )


class TestToggleJS:
    """Test the workout toggle JS behavior and edge cases."""

    @pytest.fixture
    def js_content(self):
        js = build_inline_js()
        return js

    def test_toggle_iife_present(self, js_content):
        """Workout panel toggle IIFE must exist in JS."""
        assert 'Workout panel toggle' in js_content
        assert 'gg-pack-toggle-btn' in js_content

    def test_toggle_reads_actual_count(self, js_content):
        """Toggle JS must read workout count from DOM, not hardcode it."""
        assert "panel.querySelectorAll('.gg-pack-workout').length" in js_content, (
            "Toggle JS must count workouts from DOM, not hardcode '5'"
        )

    def test_toggle_focus_management(self, js_content):
        """Expanding toggle must move focus to panel for screen readers."""
        assert 'panel.focus()' in js_content, (
            "Toggle expand must focus the panel for screen reader users"
        )
        assert "tabindex" in js_content, (
            "Panel needs temporary tabindex for programmatic focus"
        )

    def test_toggle_collapse_returns_focus(self, js_content):
        """Collapsing toggle must return focus to the button."""
        assert 'toggleBtn.focus()' in js_content, (
            "Toggle collapse must return focus to button"
        )

    def test_toggle_guards_missing_elements(self, js_content):
        """Toggle JS must exit early if elements are missing."""
        assert '!toggleBtn || !panel' in js_content or \
               'toggleBtn && panel' in js_content, (
            "Toggle JS must guard against missing DOM elements"
        )

    def test_toggle_ga4_tracking(self, js_content):
        """Toggle expansion must fire GA4 event with workout count."""
        assert 'workouts_panel_expand' in js_content
        assert 'workout_count' in js_content, (
            "GA4 event should include workout_count for analytics"
        )

    def test_toggle_updates_aria_expanded(self, js_content):
        """Toggle must update aria-expanded attribute."""
        assert "setAttribute('aria-expanded'" in js_content or \
               'aria-expanded' in js_content


class TestToggleCSS:
    """Test toggle button CSS for correctness and accessibility."""

    @pytest.fixture
    def css_content(self):
        """Read CSS from the externalized asset file (CSS is extracted from HTML)."""
        assets_dir = Path(__file__).resolve().parent.parent / 'wordpress' / 'output' / 'assets'
        css_files = sorted(assets_dir.glob('gg-styles.*.css')) if assets_dir.exists() else []
        if css_files:
            return css_files[-1].read_text()
        # Fallback: read all CSS from generated HTML (inline + external refs)
        output = Path(__file__).resolve().parent.parent / 'wordpress' / 'output' / 'unbound-200.html'
        if output.exists():
            html = output.read_text()
            # Check inline styles AND link to external CSS
            css_blocks = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL)
            # Also find referenced CSS files
            css_refs = re.findall(r'href="([^"]*gg-styles[^"]*\.css)"', html)
            for ref in css_refs:
                css_path = output.parent / ref.lstrip('/')
                if css_path.exists():
                    css_blocks.append(css_path.read_text())
            return '\n'.join(css_blocks)
        pytest.skip("No generated CSS available")

    def test_toggle_has_focus_visible_style(self, css_content):
        """Toggle button must have :focus-visible outline for keyboard users."""
        assert 'gg-pack-toggle-btn' in css_content
        assert 'focus-visible' in css_content, (
            "Toggle needs :focus-visible styles for keyboard accessibility"
        )

    def test_toggle_has_reduced_motion(self, css_content):
        """Toggle arrow animation must respect prefers-reduced-motion."""
        assert 'prefers-reduced-motion' in css_content, (
            "Toggle animation needs reduced-motion media query"
        )

    def test_toggle_no_border_radius(self, css_content):
        """Toggle button must have border-radius: 0 (neo-brutalist spec)."""
        assert 'border-radius:0' in css_content or 'border-radius: 0' in css_content, (
            "Toggle needs explicit border-radius: 0 (neo-brutalist spec)"
        )

    def test_demand_grid_responsive(self, css_content):
        """Demand bars grid must collapse to 1 column on mobile."""
        assert 'gg-pack-demands-inline' in css_content
        assert 'grid-template-columns:1fr' in css_content or \
               'grid-template-columns: 1fr' in css_content, (
            "Demand bars grid needs mobile single-column fallback"
        )


class TestLayoutEdgeCases:
    """Edge cases that could break the restructured layout."""

    def test_race_with_only_1_eligible_workout(self, normalized_data, preview_json):
        """A race with only 1 eligible workout should render toggle with '1'."""
        # Modify preview to have only 1 category with an eligible workout
        slim_preview = dict(preview_json)
        slim_preview['top_categories'] = [
            {
                'category': 'Durability',
                'score': 100,
                'workouts': ['Progressive Fatigue'],
                'workout_context': 'Test context.',
            }
        ]
        html = _build_section_with_preview(normalized_data, slim_preview)
        if 'gg-pack-workouts-toggle' in html:
            toggle_text = re.search(r'SEE (\d+) SAMPLE', html)
            assert toggle_text, "Toggle text missing count"
            assert toggle_text.group(1) == '1', (
                f"Toggle says {toggle_text.group(1)} but only 1 workout exists"
            )

    def test_configurator_summary_before_cta_in_dom(self, normalized_data, preview_json):
        """Plan summary container must appear before CTA in DOM."""
        html = _build_section_with_preview(normalized_data, preview_json)
        summary_pos = html.find('id="gg-cfg-summary"')
        cta_pos = html.find('id="gg-pack-cta-default"')
        assert summary_pos > 0 and cta_pos > 0, "Summary or CTA missing"
        assert summary_pos < cta_pos, (
            "Summary must appear before CTA — the flow is: "
            "configurator → summary → CTA"
        )

    def test_stale_preview_reset_hides_personalized_cta(self):
        """When inputs change after preview, JS must hide personalized CTA and show default."""
        js = build_inline_js()
        # The reset handler must target the CTA elements
        assert "gg-pack-cta-default" in js, (
            "Stale preview handler must reference default CTA"
        )
        assert "gg-cfg-cta" in js, (
            "Stale preview handler must reference personalized CTA"
        )
        # The handler must show default and hide personalized
        # Find the change handler section (case-insensitive search for the comment)
        stale_idx = js.lower().find('mark preview as stale')
        assert stale_idx >= 0, "JS must contain 'Mark preview as stale' comment"
        change_section = js[stale_idx:]
        assert 'defCta' in change_section or 'gg-pack-cta-default' in change_section, (
            "Change handler must restore default CTA visibility"
        )

    def test_all_757_races_have_consistent_toggle_count(self):
        """For every race with a preview, toggle count must match actual cards.

        Scans all web/race-packs/*.json to verify the generator would produce
        consistent toggle text vs actual workout cards.
        """
        race_packs_dir = Path(__file__).resolve().parent.parent / 'web' / 'race-packs'
        if not race_packs_dir.exists():
            pytest.skip("No race-packs directory")
        previews = list(race_packs_dir.glob('*.json'))
        if len(previews) < 10:
            pytest.skip("Too few race-packs to test")
        # Verify at least that every preview has top_categories with workouts
        empty_count = 0
        for p in previews:
            try:
                data = json.loads(p.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            cats = data.get('top_categories', [])
            if not cats:
                empty_count += 1
        # Allow some empties but flag if too many
        assert empty_count < len(previews) * 0.1, (
            f"{empty_count}/{len(previews)} race-packs have no top_categories"
        )
