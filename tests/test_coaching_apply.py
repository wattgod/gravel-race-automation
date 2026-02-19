"""Tests for the Gravel God coaching apply (intake form) page generator."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path so we can import the generator
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_coaching_apply import (
    FORMSUBMIT_URL,
    build_nav,
    build_header,
    build_progress_bar,
    build_section_1_basic_info,
    build_section_2_goals,
    build_section_3_fitness,
    build_section_4_recovery,
    build_section_5_equipment,
    build_section_6_schedule,
    build_section_7_work_life,
    build_section_8_health,
    build_section_9_strength,
    build_section_10_coaching_prefs,
    build_section_11_mental_game,
    build_section_12_other,
    build_submit_buttons,
    build_footer,
    build_jsonld,
    build_apply_css,
    build_apply_js,
    generate_apply_page,
)


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def apply_html():
    return generate_apply_page()


@pytest.fixture(scope="module")
def apply_css():
    return build_apply_css()


@pytest.fixture(scope="module")
def apply_js():
    return build_apply_js()


# ── Page Generation ──────────────────────────────────────────


class TestPageGeneration:
    def test_returns_html(self, apply_html):
        assert isinstance(apply_html, str)
        assert "<!DOCTYPE html>" in apply_html

    def test_has_canonical(self, apply_html):
        assert 'rel="canonical"' in apply_html
        assert "/coaching/apply/" in apply_html

    def test_has_ga4(self, apply_html):
        assert "G-EJJZ9T6M52" in apply_html
        assert "googletagmanager.com" in apply_html

    def test_has_ab_snippet(self, apply_html):
        assert "dataLayer" in apply_html

    def test_has_jsonld(self, apply_html):
        assert 'application/ld+json' in apply_html
        assert '"@type":"WebPage"' in apply_html

    def test_has_meta_robots_noindex(self, apply_html):
        assert 'name="robots"' in apply_html
        assert "noindex" in apply_html

    def test_has_meta_description(self, apply_html):
        assert 'name="description"' in apply_html

    def test_has_title(self, apply_html):
        assert "<title>" in apply_html
        assert "Coaching" in apply_html


# ── Nav ──────────────────────────────────────────────────────


class TestNav:
    def test_nav_links(self, apply_html):
        assert "/gravel-races/" in apply_html
        assert "/coaching/" in apply_html
        assert "/articles/" in apply_html
        assert "/about/" in apply_html

    def test_breadcrumb(self, apply_html):
        assert "gg-breadcrumb" in apply_html
        assert "Coaching" in apply_html
        assert "Apply" in apply_html

    def test_breadcrumb_links(self, apply_html):
        # Breadcrumb should link back to coaching page
        assert 'href="https://gravelgodcycling.com/coaching/"' in apply_html


# ── Form Structure ───────────────────────────────────────────


class TestFormStructure:
    def test_12_sections(self, apply_html):
        for i in range(1, 13):
            assert f"{i}." in apply_html

    def test_section_titles(self, apply_html):
        expected_titles = [
            "Basic Info", "Goals", "Current Fitness",
            "Recovery", "Equipment", "Schedule",
            "Work", "Health", "Strength Training",
            "Coaching Preferences", "Mental Game", "Anything Else",
        ]
        for title in expected_titles:
            assert title in apply_html

    def test_form_element(self, apply_html):
        assert '<form id="intake-form"' in apply_html
        assert "gg-apply-form-card" in apply_html

    def test_honeypot(self, apply_html):
        assert "gg-apply-honeypot" in apply_html
        assert 'name="website"' in apply_html

    def test_hidden_fields(self, apply_html):
        assert 'name="form_type"' in apply_html
        assert 'name="watts_per_kg"' in apply_html
        assert 'name="estimated_category"' in apply_html
        assert 'name="blindspots"' in apply_html
        assert 'name="inferred_traits"' in apply_html


# ── Progress Bar ─────────────────────────────────────────────


class TestProgressBar:
    def test_progress_bar_present(self, apply_html):
        assert "gg-apply-progress" in apply_html
        assert "progress-fill" in apply_html
        assert "progress-text" in apply_html


# ── Section Content ──────────────────────────────────────────


class TestSectionContent:
    def test_basic_info_fields(self):
        s = build_section_1_basic_info()
        assert 'name="name"' in s
        assert 'name="email"' in s
        assert 'name="sex"' in s
        assert 'name="age"' in s
        assert 'name="weight"' in s

    def test_goals_radio(self):
        s = build_section_2_goals()
        assert "specific_race" in s
        assert "general_fitness" in s
        assert "base_building" in s
        assert "return_from_injury" in s

    def test_race_details_conditional(self):
        s = build_section_2_goals()
        assert "gg-apply-conditional" in s
        assert 'id="race-details"' in s

    def test_fitness_wpkg_calculator(self):
        s = build_section_3_fitness()
        assert 'id="ftp"' in s
        assert 'id="calc-display"' in s
        assert "calc-wpkg" in s
        assert "calc-category" in s

    def test_fitness_longest_ride(self):
        s = build_section_3_fitness()
        assert "under-2" in s
        assert "6+" in s

    def test_recovery_baselines(self):
        s = build_section_4_recovery()
        assert 'name="rhr_baseline"' in s
        assert 'name="sleep_hours_baseline"' in s
        assert 'name="hrv_baseline"' in s
        assert 'name="sleep_quality"' in s
        assert 'name="recovery_speed"' in s

    def test_equipment_devices(self):
        s = build_section_5_equipment()
        assert 'value="whoop"' in s
        assert 'value="garmin"' in s
        assert 'value="power_meter"' in s

    def test_equipment_intervals_conditional(self):
        s = build_section_5_equipment()
        assert 'id="intervals-id-group"' in s
        assert "gg-apply-conditional" in s

    def test_schedule_days(self):
        s = build_section_6_schedule()
        assert 'name="long_ride_days"' in s
        assert 'name="interval_days"' in s
        assert 'name="off_days"' in s
        assert "flexible" in s

    def test_work_life_stress(self):
        s = build_section_7_work_life()
        assert 'name="life_stress"' in s
        assert "very_high" in s

    def test_health_fields(self):
        s = build_section_8_health()
        assert 'name="injuries"' in s
        assert 'name="medical_conditions"' in s
        assert 'name="medications"' in s

    def test_strength_options(self):
        s = build_section_9_strength()
        assert "none" in s
        assert "occasional" in s
        assert "regular" in s
        assert "dedicated" in s

    def test_coaching_prefs(self):
        s = build_section_10_coaching_prefs()
        assert 'name="checkin_frequency"' in s
        assert 'name="feedback_detail"' in s
        assert 'name="autonomy"' in s

    def test_mental_game(self):
        s = build_section_11_mental_game()
        assert "missed_workout_response" in s
        assert "make_up" in s
        assert "spiral" in s

    def test_other_section(self):
        s = build_section_12_other()
        assert 'name="previous_coach"' in s
        assert 'name="anything_else"' in s


# ── Buttons ──────────────────────────────────────────────────


class TestButtons:
    def test_submit_button(self):
        b = build_submit_buttons()
        assert "gg-apply-submit-btn" in b
        assert "Submit Questionnaire" in b

    def test_save_button(self):
        b = build_submit_buttons()
        assert "gg-apply-save-btn" in b
        assert "Save Progress" in b


# ── Brand Compliance ─────────────────────────────────────────


class TestBrandCompliance:
    def test_no_hardcoded_hex_in_css(self, apply_css):
        # Find all hex colors in the CSS
        hex_colors = re.findall(r':\s*#[0-9a-fA-F]{3,8}(?:\s|;|})', apply_css)
        # The SVG data URL in select arrow is allowed
        svg_data_hex = [h for h in hex_colors if 'data:image' not in apply_css[:apply_css.index(h.strip())] if h.strip().rstrip(';').rstrip('}') != '']
        # Filter out the SVG arrow which must use a literal hex
        css_without_svg = re.sub(r'background-image:\s*url\([^)]+\)', '', apply_css)
        remaining_hex = re.findall(r':\s*#[0-9a-fA-F]{3,8}[;\s}]', css_without_svg)
        assert len(remaining_hex) == 0, f"Found hardcoded hex in CSS: {remaining_hex}"

    def test_no_border_radius(self, apply_css):
        assert "border-radius" not in apply_css

    def test_no_box_shadow(self, apply_css):
        assert "box-shadow" not in apply_css

    def test_no_opacity_transition(self, apply_css):
        assert "opacity" not in apply_css.lower()

    def test_uses_brand_tokens(self, apply_css):
        assert "var(--gg-color-" in apply_css
        assert "var(--gg-font-" in apply_css
        assert "var(--gg-spacing-" in apply_css

    def test_no_bounce_easing(self, apply_css):
        assert "bounce" not in apply_css.lower()
        assert "spring" not in apply_css.lower()

    def test_correct_class_prefix(self, apply_css):
        # All custom classes should use gg-apply- prefix
        class_matches = re.findall(r'\.(gg-[a-z]+-)', apply_css)
        for cls in class_matches:
            assert cls.startswith("gg-apply-") or cls.startswith("gg-neo-") or cls.startswith("gg-site-"), \
                f"Non-prefixed class: {cls}"

    def test_no_entrance_animations(self, apply_css):
        assert "@keyframes" not in apply_css
        assert "animation:" not in apply_css

    def test_two_voice_typography(self, apply_css):
        assert "var(--gg-font-data)" in apply_css
        assert "var(--gg-font-editorial)" in apply_css


# ── GA4 Events ───────────────────────────────────────────────


class TestGA4Events:
    def test_page_view_event(self, apply_js):
        assert "apply_page_view" in apply_js

    def test_scroll_depth_event(self, apply_js):
        assert "apply_scroll_depth" in apply_js

    def test_form_submitted_event(self, apply_js):
        assert "apply_form_submitted" in apply_js

    def test_progress_saved_event(self, apply_js):
        assert "apply_progress_saved" in apply_js

    def test_wpkg_calculated_event(self, apply_js):
        assert "apply_wpkg_calculated" in apply_js


# ── JavaScript Features ──────────────────────────────────────


class TestJSFeatures:
    def test_wpkg_categories(self, apply_js):
        assert "CATEGORIES_MALE" in apply_js
        assert "CATEGORIES_FEMALE" in apply_js

    def test_blindspot_inference(self, apply_js):
        assert "inferTraits" in apply_js
        assert "Recovery Deficit" in apply_js
        assert "Life Stress Overload" in apply_js
        assert "Movement Quality Gap" in apply_js
        assert "Injury Management" in apply_js
        assert "Time-Crunched" in apply_js
        assert "Masters Recovery" in apply_js
        assert "Overtraining Risk" in apply_js

    def test_progress_tracking(self, apply_js):
        assert "updateProgress" in apply_js
        assert "progress-fill" in apply_js

    def test_save_restore(self, apply_js):
        assert "localStorage" in apply_js
        assert "athlete_questionnaire_progress" in apply_js
        assert "restoreProgress" in apply_js

    def test_conditional_fields(self, apply_js):
        assert "handleConditionals" in apply_js
        assert "race-details" in apply_js
        assert "intervals-id-group" in apply_js

    def test_flexible_checkbox_logic(self, apply_js):
        assert "flexible" in apply_js

    def test_formsubmit_submission(self, apply_js):
        assert FORMSUBMIT_URL in apply_js
        assert "formsubmit.co" in apply_js

    def test_mailto_fallback(self, apply_js):
        assert "mailto:gravelgodcoaching@gmail.com" in apply_js

    def test_format_submission(self, apply_js):
        assert "formatSubmission" in apply_js
        assert "# Athlete Intake:" in apply_js


# ── JS Syntax Validation ─────────────────────────────────────


class TestJSSyntax:
    def test_js_parses_via_node(self, apply_js):
        js = apply_js.replace("<script>", "").replace("</script>", "")
        test_script = f"""
try {{
    new Function({json.dumps(js)});
    console.log('SYNTAX_OK');
}} catch(e) {{
    console.log('SYNTAX_ERROR: ' + e.message);
    process.exit(1);
}}
"""
        result = subprocess.run(
            ["node", "-e", test_script],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f"JS syntax error: {result.stderr or result.stdout}"
        assert "SYNTAX_OK" in result.stdout


# ── JSON-LD ──────────────────────────────────────────────────


class TestJSONLD:
    def test_jsonld_structure(self):
        jsonld_html = build_jsonld()
        assert 'application/ld+json' in jsonld_html
        # Extract JSON from script tag
        json_str = jsonld_html.split(">", 1)[1].rsplit("<", 1)[0]
        data = json.loads(json_str)
        assert data["@type"] == "WebPage"
        assert "/coaching/apply/" in data["url"]

    def test_breadcrumb_in_jsonld(self):
        jsonld_html = build_jsonld()
        json_str = jsonld_html.split(">", 1)[1].rsplit("<", 1)[0]
        data = json.loads(json_str)
        assert "breadcrumb" in data
        items = data["breadcrumb"]["itemListElement"]
        assert len(items) == 3
        assert items[0]["name"] == "Home"
        assert items[1]["name"] == "Coaching"
        assert items[2]["name"] == "Apply"


# ── Footer ───────────────────────────────────────────────────


class TestFooter:
    def test_footer_present(self, apply_html):
        assert "gg-site-footer" in apply_html

    def test_confidential_notice(self, apply_html):
        assert "confidential" in apply_html.lower()
        assert "gravelgodcoaching@gmail.com" in apply_html
