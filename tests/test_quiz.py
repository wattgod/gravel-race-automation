"""Tests for wordpress/generate_quiz.py — race finder quiz page generator."""

import json
import re
import sys
from pathlib import Path

import pytest

# Ensure wordpress/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

from generate_quiz import (
    build_quiz_css,
    build_quiz_js,
    build_quiz_page,
    esc,
    load_race_index,
    FUELING_WORKER_URL,
)
from brand_tokens import GA_MEASUREMENT_ID


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def race_index():
    """Load the real race index for testing."""
    return load_race_index()


@pytest.fixture
def sample_races():
    """Minimal synthetic race list for fast tests that don't need real data."""
    return [
        {
            "slug": "test-gravel-100",
            "name": "Test Gravel 100",
            "tier": 2,
            "final_score": 72,
            "location": "Emporia, Kansas",
            "state": "Kansas",
            "region": "Midwest",
            "country": "US",
            "distance_mi": 100,
            "elevation_ft": 5000,
            "month_num": 6,
            "difficulty_composite": 3.2,
            "technicality": 3,
            "terrain_primary": "mixed",
            "discipline": "gravel",
        },
        {
            "slug": "unbound-200",
            "name": "Unbound Gravel 200",
            "tier": 1,
            "final_score": 80,
            "location": "Emporia, Kansas",
            "state": "Kansas",
            "region": "Midwest",
            "country": "US",
            "distance_mi": 200,
            "elevation_ft": 11000,
            "month_num": 6,
            "difficulty_composite": 4.8,
            "technicality": 3,
            "terrain_primary": "gravel",
            "discipline": "gravel",
        },
        {
            "slug": "mid-south-100",
            "name": "Mid South 100",
            "tier": 1,
            "final_score": 83,
            "location": "Stillwater, Oklahoma",
            "state": "Oklahoma",
            "region": "South",
            "country": "US",
            "distance_mi": 100,
            "elevation_ft": 4500,
            "month_num": 3,
            "difficulty_composite": 3.5,
            "technicality": 2,
            "terrain_primary": "mixed",
            "discipline": "gravel",
        },
    ]


@pytest.fixture
def quiz_html(sample_races):
    """Pre-built quiz page HTML from sample races."""
    return build_quiz_page(sample_races)


@pytest.fixture
def real_quiz_html(race_index):
    """Quiz page HTML built from the real race index."""
    return build_quiz_page(race_index)


# ── load_race_index ──────────────────────────────────────────


class TestLoadRaceIndex:
    def test_loads_valid_data(self):
        races = load_race_index()
        assert isinstance(races, list)
        assert len(races) > 0

    def test_races_have_required_fields(self):
        races = load_race_index()
        for r in races[:10]:  # Spot-check first 10
            assert "slug" in r, f"Race missing slug: {r.get('name', 'unknown')}"
            assert "name" in r, f"Race missing name: {r.get('slug', 'unknown')}"

    def test_race_count_reasonable(self):
        """Database should have a substantial number of races."""
        races = load_race_index()
        assert len(races) >= 100, f"Only {len(races)} races — expected 100+"


# ── build_quiz_page — HTML structure ─────────────────────────


class TestQuizPageStructure:
    def test_returns_valid_html(self, quiz_html):
        assert quiz_html.startswith("<!DOCTYPE html>")
        assert "</html>" in quiz_html
        assert "<head>" in quiz_html
        assert "<body>" in quiz_html

    def test_has_all_5_steps(self, quiz_html):
        for step in range(1, 6):
            assert f'data-step="{step}"' in quiz_html, f"Missing step {step}"

    def test_steps_have_data_step_attributes_1_through_5(self, quiz_html):
        steps = re.findall(r'data-step="(\d+)"', quiz_html)
        assert sorted(set(steps)) == ["1", "2", "3", "4", "5"]

    def test_each_step_has_data_field_attribute(self, quiz_html):
        expected_fields = {"difficulty", "distance", "terrain", "region", "timing"}
        found_fields = set(re.findall(r'data-field="(\w+)"', quiz_html))
        assert expected_fields.issubset(found_fields), (
            f"Missing fields: {expected_fields - found_fields}"
        )

    def test_step_1_difficulty(self, quiz_html):
        assert 'data-field="difficulty"' in quiz_html
        assert 'data-value="easy"' in quiz_html
        assert 'data-value="moderate"' in quiz_html
        assert 'data-value="hard"' in quiz_html
        assert 'data-value="brutal"' in quiz_html

    def test_step_2_distance(self, quiz_html):
        assert 'data-field="distance"' in quiz_html
        assert 'data-value="short"' in quiz_html
        assert 'data-value="medium"' in quiz_html
        assert 'data-value="long"' in quiz_html
        assert 'data-value="ultra"' in quiz_html

    def test_step_3_terrain(self, quiz_html):
        assert 'data-field="terrain"' in quiz_html
        assert 'data-value="smooth"' in quiz_html
        assert 'data-value="mixed"' in quiz_html
        assert 'data-value="technical"' in quiz_html

    def test_step_4_region(self, quiz_html):
        assert 'data-field="region"' in quiz_html
        assert 'data-value="west"' in quiz_html
        assert 'data-value="central"' in quiz_html
        assert 'data-value="east"' in quiz_html

    def test_step_5_timing(self, quiz_html):
        assert 'data-field="timing"' in quiz_html
        assert 'data-value="spring"' in quiz_html
        assert 'data-value="summer"' in quiz_html
        assert 'data-value="fall"' in quiz_html

    def test_has_email_gate(self, quiz_html):
        assert 'id="gg-quiz-gate"' in quiz_html
        assert 'id="gg-quiz-gate-form"' in quiz_html
        assert 'type="email"' in quiz_html

    def test_has_results_container(self, quiz_html):
        assert 'id="gg-quiz-results"' in quiz_html
        assert 'id="gg-quiz-results-list"' in quiz_html

    def test_has_progress_bar(self, quiz_html):
        assert 'id="gg-quiz-progress"' in quiz_html
        assert 'id="gg-quiz-progress-bar"' in quiz_html
        assert "gg-quiz-progress-bar" in quiz_html


# ── Email gate honeypot ──────────────────────────────────────


class TestEmailGateHoneypot:
    def test_honeypot_field_present(self, quiz_html):
        assert 'name="website"' in quiz_html

    def test_honeypot_field_has_empty_value(self, quiz_html):
        assert 'name="website" value=""' in quiz_html

    def test_honeypot_is_hidden_input(self, quiz_html):
        # The honeypot should be a hidden input
        assert 'type="hidden" name="website" value=""' in quiz_html

    def test_source_field_is_race_quiz(self, quiz_html):
        assert 'name="source" value="race_quiz"' in quiz_html


# ── JSON-LD: BreadcrumbList ──────────────────────────────────


class TestBreadcrumbJsonLD:
    def test_breadcrumb_jsonld_present(self, quiz_html):
        assert "application/ld+json" in quiz_html
        assert "BreadcrumbList" in quiz_html

    def test_breadcrumb_has_3_items(self, quiz_html):
        # Extract JSON-LD blocks
        jsonld_blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            quiz_html,
            re.DOTALL,
        )
        breadcrumb = None
        for block in jsonld_blocks:
            data = json.loads(block)
            if data.get("@type") == "BreadcrumbList":
                breadcrumb = data
                break
        assert breadcrumb is not None, "BreadcrumbList JSON-LD not found"
        assert len(breadcrumb["itemListElement"]) == 3

    def test_breadcrumb_positions(self, quiz_html):
        jsonld_blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            quiz_html,
            re.DOTALL,
        )
        for block in jsonld_blocks:
            data = json.loads(block)
            if data.get("@type") == "BreadcrumbList":
                items = data["itemListElement"]
                assert items[0]["position"] == 1
                assert items[0]["name"] == "Home"
                assert items[1]["position"] == 2
                assert items[1]["name"] == "Gravel Races"
                assert items[2]["position"] == 3
                assert items[2]["name"] == "Race Finder Quiz"
                return
        pytest.fail("BreadcrumbList not found")


# ── JSON-LD: FAQPage ────────────────────────────────────────


class TestFAQJsonLD:
    def test_faq_jsonld_present(self, quiz_html):
        assert "FAQPage" in quiz_html

    def test_faq_has_questions(self, quiz_html):
        jsonld_blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            quiz_html,
            re.DOTALL,
        )
        faq = None
        for block in jsonld_blocks:
            data = json.loads(block)
            if data.get("@type") == "FAQPage":
                faq = data
                break
        assert faq is not None, "FAQPage JSON-LD not found"
        assert "mainEntity" in faq
        assert len(faq["mainEntity"]) >= 3, "Expected at least 3 FAQ questions"

    def test_faq_questions_have_answers(self, quiz_html):
        jsonld_blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            quiz_html,
            re.DOTALL,
        )
        for block in jsonld_blocks:
            data = json.loads(block)
            if data.get("@type") == "FAQPage":
                for q in data["mainEntity"]:
                    assert q["@type"] == "Question"
                    assert "name" in q
                    assert "acceptedAnswer" in q
                    assert q["acceptedAnswer"]["@type"] == "Answer"
                    assert len(q["acceptedAnswer"]["text"]) > 0
                return
        pytest.fail("FAQPage not found")

    def test_faq_uses_actual_race_count(self, sample_races):
        """FAQ text should reference the actual race count, not a hardcoded number."""
        html = build_quiz_page(sample_races)
        race_count = len(sample_races)
        jsonld_blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        for block in jsonld_blocks:
            data = json.loads(block)
            if data.get("@type") == "FAQPage":
                # At least one answer should mention the actual race count
                texts = [q["acceptedAnswer"]["text"] for q in data["mainEntity"]]
                combined = " ".join(texts)
                assert str(race_count) in combined, (
                    f"FAQ answers should mention actual race count ({race_count})"
                )
                return
        pytest.fail("FAQPage not found")


# ── Meta description / og:description — dynamic race count ───


class TestMetaDescriptions:
    def test_meta_description_uses_actual_race_count(self, sample_races):
        html = build_quiz_page(sample_races)
        race_count = str(len(sample_races))
        # Extract meta description
        match = re.search(r'name="description" content="([^"]+)"', html)
        assert match is not None, "Meta description not found"
        assert race_count in match.group(1), (
            f"Meta description should contain actual race count ({race_count}), "
            f"got: {match.group(1)}"
        )

    def test_og_description_uses_actual_race_count(self, sample_races):
        html = build_quiz_page(sample_races)
        race_count = str(len(sample_races))
        match = re.search(r'og:description" content="([^"]+)"', html)
        assert match is not None, "og:description not found"
        assert race_count in match.group(1), (
            f"og:description should contain actual race count ({race_count}), "
            f"got: {match.group(1)}"
        )

    def test_meta_description_not_hardcoded_328(self, sample_races):
        """With 3 sample races, meta should NOT say 328."""
        html = build_quiz_page(sample_races)
        match = re.search(r'name="description" content="([^"]+)"', html)
        assert match is not None
        # sample_races has 3 races, not 328
        assert "328" not in match.group(1), "Meta description appears hardcoded to 328"

    def test_og_description_not_hardcoded_328(self, sample_races):
        html = build_quiz_page(sample_races)
        match = re.search(r'og:description" content="([^"]+)"', html)
        assert match is not None
        assert "328" not in match.group(1), "og:description appears hardcoded to 328"

    def test_real_race_count_in_meta(self, race_index, real_quiz_html):
        """Real race index should have its actual count in meta descriptions."""
        race_count = str(len(race_index))
        match = re.search(r'name="description" content="([^"]+)"', real_quiz_html)
        assert match is not None
        assert race_count in match.group(1), (
            f"Expected race count {race_count} in meta description"
        )


# ── Worker URL ───────────────────────────────────────────────


class TestWorkerURL:
    def test_worker_url_present_in_page(self, quiz_html):
        assert FUELING_WORKER_URL in quiz_html

    def test_worker_url_assigned_to_var(self, quiz_html):
        assert f"WORKER_URL='{FUELING_WORKER_URL}'" in quiz_html


# ── GA4 ──────────────────────────────────────────────────────


class TestGA4:
    def test_ga4_measurement_id_present(self, quiz_html):
        assert GA_MEASUREMENT_ID in quiz_html

    def test_ga4_script_tag(self, quiz_html):
        assert "googletagmanager.com/gtag/js" in quiz_html

    def test_ga4_config_call(self, quiz_html):
        assert f"gtag('config','{GA_MEASUREMENT_ID}')" in quiz_html


# ── build_quiz_css ───────────────────────────────────────────


class TestQuizCSS:
    def test_returns_non_empty_string(self):
        css = build_quiz_css()
        assert isinstance(css, str)
        assert len(css) > 100

    def test_has_page_selector(self):
        css = build_quiz_css()
        assert ".gg-quiz-page" in css

    def test_has_step_selector(self):
        css = build_quiz_css()
        assert ".gg-quiz-step" in css

    def test_has_option_selector(self):
        css = build_quiz_css()
        assert ".gg-quiz-option" in css

    def test_has_progress_selectors(self):
        css = build_quiz_css()
        assert ".gg-quiz-progress" in css
        assert ".gg-quiz-progress-bar" in css

    def test_has_gate_selectors(self):
        css = build_quiz_css()
        assert ".gg-quiz-gate" in css
        assert ".gg-quiz-gate-btn" in css
        assert ".gg-quiz-gate-input" in css
        assert ".gg-quiz-gate-row" in css

    def test_has_results_selectors(self):
        css = build_quiz_css()
        assert ".gg-quiz-results" in css
        assert ".gg-quiz-result-card" in css

    def test_has_header_selector(self):
        css = build_quiz_css()
        assert ".gg-quiz-header" in css

    def test_has_footer_selector(self):
        css = build_quiz_css()
        assert ".gg-quiz-footer" in css

    def test_has_responsive_breakpoint(self):
        css = build_quiz_css()
        assert "@media (max-width:600px)" in css

    def test_has_animation_keyframes(self):
        css = build_quiz_css()
        assert "@keyframes" in css
        assert "gg-quiz-slide-in" in css

    def test_has_selected_state(self):
        css = build_quiz_css()
        assert ".is-selected" in css


# ── build_quiz_js ────────────────────────────────────────────


class TestQuizJS:
    def test_returns_non_empty_string(self):
        js = build_quiz_js()
        assert isinstance(js, str)
        assert len(js) > 100

    def test_has_score_race_function(self):
        js = build_quiz_js()
        assert "scoreRace" in js

    def test_has_show_step_function(self):
        js = build_quiz_js()
        assert "showStep" in js

    def test_has_show_results_function(self):
        js = build_quiz_js()
        assert "showResults" in js

    def test_has_compute_and_gate_function(self):
        js = build_quiz_js()
        assert "computeAndGate" in js

    def test_has_restart_handler(self):
        js = build_quiz_js()
        assert "gg-quiz-restart" in js

    def test_has_ga4_event_tracking(self):
        js = build_quiz_js()
        assert "quiz_step" in js
        assert "quiz_complete" in js
        assert "email_capture" in js

    def test_has_localstorage_caching(self):
        js = build_quiz_js()
        assert "localStorage" in js
        assert "gg-pk-fueling" in js

    def test_scoring_checks_difficulty(self):
        js = build_quiz_js()
        assert "ans.difficulty" in js

    def test_scoring_checks_distance(self):
        js = build_quiz_js()
        assert "ans.distance" in js

    def test_scoring_checks_terrain(self):
        js = build_quiz_js()
        assert "ans.terrain" in js

    def test_scoring_checks_region(self):
        js = build_quiz_js()
        assert "ans.region" in js

    def test_scoring_checks_timing(self):
        js = build_quiz_js()
        assert "ans.timing" in js

    def test_tier_bonus_in_scoring(self):
        """Higher-tier races should get a scoring bonus."""
        js = build_quiz_js()
        assert "r.t===1" in js
        assert "r.t===2" in js


# ── Shared results URL enforces email gate ───────────────────


class TestSharedResultsEmailGate:
    def test_shared_results_checks_cached_email(self):
        """Shared results URL (?results=) must check for cached email."""
        js = build_quiz_js()
        assert "hasCachedEmail" in js

    def test_shared_results_shows_email_gate(self):
        """If no cached email, shared results should show the gate."""
        js = build_quiz_js()
        # After checking hasCachedEmail, the code should show the gate
        assert "gg-quiz-gate" in js
        # The JS should handle the results parameter
        assert "results" in js

    def test_shared_results_url_parameter_parsed(self):
        js = build_quiz_js()
        assert "URLSearchParams" in js
        assert "resultSlugs" in js or "results" in js

    def test_shared_results_source_quiz_shared(self):
        """Shared results should use 'quiz_shared' as the source."""
        js = build_quiz_js()
        assert "quiz_shared" in js


# ── Race data JS array ───────────────────────────────────────


class TestRaceDataJS:
    def test_races_var_in_page(self, quiz_html):
        assert "var RACES=" in quiz_html

    def test_race_slugs_in_js(self, quiz_html):
        assert "test-gravel-100" in quiz_html
        assert "unbound-200" in quiz_html
        assert "mid-south-100" in quiz_html

    def test_race_names_in_js(self, quiz_html):
        assert "Test Gravel 100" in quiz_html
        assert "Unbound Gravel 200" in quiz_html

    def test_race_data_has_required_fields(self, sample_races):
        """Verify the JS race data includes all fields needed for scoring."""
        html = build_quiz_page(sample_races)
        # Extract the RACES JSON from the page
        match = re.search(r'var RACES=(\[.*?\]);', html, re.DOTALL)
        assert match is not None, "RACES variable not found in page"
        races_json = match.group(1)
        races = json.loads(races_json)
        assert len(races) == len(sample_races)
        for r in races:
            assert "s" in r  # slug
            assert "n" in r  # name
            assert "t" in r  # tier
            assert "dm" in r  # distance_mi
            assert "df" in r  # difficulty
            assert "tc" in r  # technicality
            assert "mn" in r  # month_num
            assert "rg" in r  # region
            assert "di" in r  # discipline


# ── Brand tokens & styles ────────────────────────────────────


class TestBrandTokens:
    def test_page_has_css_custom_properties(self, quiz_html):
        assert "--gg-color-primary-brown" in quiz_html
        assert "--gg-font-data" in quiz_html

    def test_page_has_font_face(self, quiz_html):
        assert "@font-face" in quiz_html
        assert "Sometype Mono" in quiz_html


# ── Utility functions ────────────────────────────────────────


class TestEsc:
    def test_escapes_html(self):
        assert esc("<script>") == "&lt;script&gt;"

    def test_escapes_ampersand(self):
        assert esc("Flint & Hills") == "Flint &amp; Hills"

    def test_handles_none(self):
        assert esc(None) == ""

    def test_handles_empty_string(self):
        assert esc("") == ""

    def test_handles_number(self):
        assert esc(42) == "42"


# ── Integration: real race index ─────────────────────────────


class TestRealRaceIntegration:
    """Tests that run against the actual race-index.json to catch
    real-world issues with the quiz page generator."""

    def test_real_page_generates_without_error(self, race_index):
        html = build_quiz_page(race_index)
        assert html.startswith("<!DOCTYPE html>")
        assert len(html) > 1000

    def test_real_page_has_all_5_steps(self, real_quiz_html):
        for step in range(1, 6):
            assert f'data-step="{step}"' in real_quiz_html

    def test_real_page_has_email_gate(self, real_quiz_html):
        assert 'id="gg-quiz-gate"' in real_quiz_html

    def test_real_page_has_results(self, real_quiz_html):
        assert 'id="gg-quiz-results"' in real_quiz_html

    def test_real_page_race_count_in_meta(self, race_index, real_quiz_html):
        count = str(len(race_index))
        assert count in real_quiz_html, (
            f"Real race count ({count}) not found in page HTML"
        )
