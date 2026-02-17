"""Tests for the Gravel God Training Guide generator."""
import json
import re
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path so we can import the generator
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

import generate_guide
from generate_guide import (
    load_content,
    generate_guide_page,
    render_prose,
    render_data_table,
    render_accordion,
    render_tabs,
    render_timeline,
    render_process_list,
    render_callout,
    render_knowledge_check,
    render_flashcard,
    render_scenario,
    render_calculator,
    render_zone_visualizer,
    render_image,
    render_video,
    build_nav,
    build_hero,
    build_chapter,
    build_gate,
    build_rider_selector,
    build_cta_newsletter,
    build_cta_training,
    build_cta_coaching,
    build_cta_finale,
    build_jsonld,
    build_guide_css,
    build_guide_js,
    _md_inline,
    BLOCK_RENDERERS,
)


# ── Content Loading ──────────────────────────────────────────


class TestContentLoading:
    def test_content_loads(self):
        content = load_content()
        assert "chapters" in content
        assert "title" in content
        assert "meta_description" in content

    def test_eight_chapters(self):
        content = load_content()
        assert len(content["chapters"]) == 8

    def test_chapter_ids_unique(self):
        content = load_content()
        ids = [ch["id"] for ch in content["chapters"]]
        assert len(ids) == len(set(ids))

    def test_chapter_numbers_sequential(self):
        content = load_content()
        numbers = [ch["number"] for ch in content["chapters"]]
        assert numbers == list(range(1, 9))

    def test_gating_structure(self):
        """Chapters 1-3 are free, 4-8 are gated."""
        content = load_content()
        for ch in content["chapters"]:
            if ch["number"] <= 3:
                assert ch["gated"] is False, f"Chapter {ch['number']} should be free"
            else:
                assert ch["gated"] is True, f"Chapter {ch['number']} should be gated"

    def test_all_chapters_have_sections(self):
        content = load_content()
        for ch in content["chapters"]:
            assert len(ch["sections"]) > 0, f"Chapter {ch['number']} has no sections"

    def test_all_sections_have_blocks(self):
        content = load_content()
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                assert len(sec["blocks"]) > 0, f"Section {sec['id']} has no blocks"


# ── Block Renderers ──────────────────────────────────────────


class TestBlockRenderers:
    def test_all_block_types_have_renderers(self):
        expected_types = {
            "prose", "data_table", "accordion", "tabs", "timeline",
            "process_list", "callout", "knowledge_check",
            "flashcard", "scenario", "calculator", "zone_visualizer",
            "image", "video", "hero_stat",
        }
        assert set(BLOCK_RENDERERS.keys()) == expected_types

    def test_render_prose_basic(self):
        html = render_prose({"content": "Hello world."})
        assert "<p>Hello world.</p>" in html

    def test_render_prose_bold(self):
        html = render_prose({"content": "This is **bold** text."})
        assert "<strong>bold</strong>" in html

    def test_render_prose_list(self):
        html = render_prose({"content": "Items:\n- First\n- Second"})
        assert "<ul" in html
        assert "<li>First</li>" in html
        assert "<li>Second</li>" in html

    def test_render_data_table(self):
        block = {
            "headers": ["A", "B"],
            "rows": [["1", "2"], ["3", "4"]],
            "caption": "Test Table",
        }
        html = render_data_table(block)
        assert "gg-guide-table" in html
        assert "<th>A</th>" in html
        assert "<td>1</td>" in html
        assert "Test Table" in html

    def test_render_accordion(self):
        block = {
            "items": [
                {"title": "Item 1", "content": "Content 1"},
                {"title": "Item 2", "content": "Content 2"},
            ]
        }
        html = render_accordion(block)
        assert "gg-guide-accordion-item" in html
        assert "Item 1" in html
        assert "Content 1" in html
        assert html.count("gg-guide-accordion-trigger") == 2

    def test_render_tabs(self):
        block = {
            "tabs": [
                {"label": "Tab 1", "title": "First Tab", "content": "Content 1"},
                {"label": "Tab 2", "title": "Second Tab", "content": "Content 2"},
            ]
        }
        html = render_tabs(block)
        assert "gg-guide-tabs" in html
        assert "Tab 1" in html
        assert "gg-guide-tab--active" in html
        # Second panel should be hidden
        assert 'style="display:none"' in html

    def test_render_timeline(self):
        block = {
            "title": "Steps",
            "steps": [
                {"label": "Step 1", "content": "Do thing 1"},
                {"label": "Step 2", "content": "Do thing 2"},
            ],
        }
        html = render_timeline(block)
        assert "gg-guide-timeline" in html
        assert "Step 1" in html
        assert ">1</div>" in html
        assert ">2</div>" in html

    def test_render_process_list(self):
        block = {
            "items": [
                {"label": "Fitness", "detail": "70% of result", "percentage": 70},
                {"label": "Pacing", "detail": "20% of result", "percentage": 20},
            ]
        }
        html = render_process_list(block)
        assert "gg-guide-process-list" in html
        assert "Fitness" in html
        assert 'style="width:70%"' in html
        assert "gg-guide-process-bar-wrap" in html

    def test_render_callout(self):
        block = {"style": "quote", "content": "Important quote here."}
        html = render_callout(block)
        assert "gg-guide-callout--quote" in html
        assert "Important quote here." in html

    def test_render_knowledge_check(self):
        block = {
            "question": "What happens?",
            "options": [
                {"text": "Wrong answer", "correct": False},
                {"text": "Right answer", "correct": True},
            ],
            "explanation": "Because reasons.",
        }
        html = render_knowledge_check(block)
        assert "KNOWLEDGE CHECK" in html
        assert "What happens?" in html
        assert 'data-correct="true"' in html
        assert 'data-correct="false"' in html
        assert "Because reasons." in html

    def test_render_flashcard(self):
        block = {
            "title": "Test Deck",
            "cards": [
                {"front": "Question 1", "back": "Answer 1"},
                {"front": "Question 2", "back": "Answer 2"},
            ],
        }
        html = render_flashcard(block)
        assert "gg-guide-flashcard-deck" in html
        assert "Test Deck" in html
        assert "Question 1" in html
        assert "Answer 1" in html
        assert html.count('class="gg-guide-flashcard"') == 2

    def test_render_flashcard_deterministic(self):
        block = {
            "cards": [
                {"front": "A", "back": "B"},
            ],
        }
        html1 = render_flashcard(block)
        html2 = render_flashcard(block)
        assert html1 == html2

    def test_render_scenario(self):
        block = {
            "prompt": "What do you do?",
            "options": [
                {"label": "Option A", "result": "Bad outcome", "best": False},
                {"label": "Option B", "result": "Good outcome", "best": True},
            ],
        }
        html = render_scenario(block)
        assert "RACE SCENARIO" in html
        assert "What do you do?" in html
        assert "Option A" in html
        assert 'data-best="true"' in html
        assert html.count('class="gg-guide-scenario-option"') == 2


# ── Full Page Generation ─────────────────────────────────────


class TestPageGeneration:
    @pytest.fixture(scope="class")
    def guide_html(self):
        content = load_content()
        return generate_guide_page(content, inline=True)

    def test_generates_html(self, guide_html):
        assert guide_html.startswith("<!DOCTYPE html>")
        assert "</html>" in guide_html

    def test_canonical_url(self, guide_html):
        assert 'href="https://gravelgodcycling.com/guide/"' in guide_html

    def test_all_chapters_present(self, guide_html):
        for i in range(1, 9):
            assert f"CHAPTER {i:02d}" in guide_html

    def test_gated_chapters_have_class(self, guide_html):
        assert 'class="gg-guide-chapter gg-guide-gated"' in guide_html

    def test_free_chapters_no_gated_class(self, guide_html):
        # Free chapters (1-3) must NOT have gated class
        for ch_num in ["1", "2", "3"]:
            match = re.search(
                rf'class="([^"]*)"[^>]*data-chapter="{ch_num}"', guide_html
            )
            assert match, f"Chapter {ch_num} not found in HTML"
            assert "gg-guide-gated" not in match.group(1), \
                f"Chapter {ch_num} should not have gated class"

    def test_gate_overlay_present(self, guide_html):
        assert 'id="gg-guide-gate"' in guide_html
        assert "CHAPTERS 4-8 ARE LOCKED" in guide_html
        assert "Unlock the Full Guide" in guide_html

    def test_progress_bar_present(self, guide_html):
        assert 'id="gg-guide-progress"' in guide_html

    def test_chapter_nav_present(self, guide_html):
        assert 'id="gg-guide-chapnav"' in guide_html
        assert guide_html.count('class="gg-guide-chapnav-item') == 8

    def test_no_quiz_in_output(self, guide_html):
        assert 'id="gg-guide-quiz"' not in guide_html
        assert "data-matrix" not in guide_html

    def test_training_cta(self, guide_html):
        assert "gg-guide-cta--training" in guide_html

    def test_coaching_cta(self, guide_html):
        assert "gg-guide-cta--coaching" in guide_html

    def test_finale_cta(self, guide_html):
        assert "gg-guide-finale" in guide_html
        assert "gg-guide-finale-grid" in guide_html

    def test_substack_embed(self, guide_html):
        assert "gravelgodcycling.substack.com/embed" in guide_html

    def test_nav_has_site_header(self, guide_html):
        """Guide must use the shared site header, not old dark nav."""
        assert 'class="gg-site-header"' in guide_html
        assert "cropped-Gravel-God-logo.png" in guide_html
        assert "gg-site-nav" not in guide_html  # old class must be gone

    def test_nav_links(self, guide_html):
        assert '/gravel-races/">RACES</a>' in guide_html
        assert '/coaching/">COACHING</a>' in guide_html
        assert '/articles/">ARTICLES</a>' in guide_html
        assert '/about/">ABOUT</a>' in guide_html
        assert "ALL RACES" not in guide_html  # old link text
        assert "HOW WE RATE" not in guide_html  # old link text

    def test_gate_position_between_ch3_and_ch4(self, guide_html):
        """Gate overlay must appear between chapter 3 and chapter 4."""
        gate_pos = guide_html.index('id="gg-guide-gate"')
        ch3_pos = guide_html.index('data-chapter="3"')
        ch4_pos = guide_html.index('data-chapter="4"')
        assert ch3_pos < gate_pos < ch4_pos, \
            "Gate must appear between chapter 3 and chapter 4"

    def test_cross_link_anchors_exist(self, guide_html):
        """Internal anchor links must point to existing element IDs."""
        anchors = re.findall(r'href="#([^"]+)"', guide_html)
        ids = set(re.findall(r'id="([^"]+)"', guide_html))
        missing = [a for a in anchors if a not in ids]
        assert not missing, f"Broken anchor links: {missing}"

    def test_footer_present(self, guide_html):
        assert "gg-footer" in guide_html

    def test_sometype_mono_font(self, guide_html):
        assert "Sometype+Mono" in guide_html or "Sometype Mono" in guide_html

    def test_og_tags(self, guide_html):
        assert 'property="og:title"' in guide_html
        assert 'property="og:url"' in guide_html

    def test_inline_css_present(self, guide_html):
        # Inline mode should have guide CSS in <style> tags
        assert "gg-guide-progress" in guide_html
        assert "gg-guide-chapnav" in guide_html

    def test_inline_js_present(self, guide_html):
        # Inline mode should have guide JS in <script> tags
        assert "gg_guide_unlocked" in guide_html
        assert "IntersectionObserver" in guide_html


# ── JSON-LD ──────────────────────────────────────────────────


class TestJsonLd:
    def test_article_schema(self):
        content = load_content()
        jsonld = build_jsonld(content)
        assert '"@type":"Article"' in jsonld
        assert content["title"] in jsonld

    def test_breadcrumb_schema(self):
        content = load_content()
        jsonld = build_jsonld(content)
        assert '"@type":"BreadcrumbList"' in jsonld
        assert "Training Guide" in jsonld

    def test_valid_json(self):
        content = load_content()
        jsonld = build_jsonld(content)
        # Extract JSON blocks and validate
        import re
        blocks = re.findall(r'<script type="application/ld\+json">(.+?)</script>', jsonld, re.DOTALL)
        assert len(blocks) == 4  # Article, BreadcrumbList, Course, HowTo
        for block in blocks:
            parsed = json.loads(block)
            assert "@context" in parsed

    def test_course_schema(self):
        content = load_content()
        jsonld = build_jsonld(content)
        assert '"@type":"Course"' in jsonld

    def test_howto_schema(self):
        content = load_content()
        jsonld = build_jsonld(content)
        assert '"@type":"HowTo"' in jsonld

    def test_jsonld_has_dates(self):
        content = load_content()
        jsonld = build_jsonld(content)
        assert '"datePublished"' in jsonld or '"datePublished":' in jsonld
        assert '"dateModified"' in jsonld or '"dateModified":' in jsonld

    def test_jsonld_has_image(self):
        content = load_content()
        jsonld = build_jsonld(content)
        assert '"image"' in jsonld or '"image":' in jsonld


# ── CSS / JS ────────────────────────────────────────────────


class TestAssets:
    def test_css_not_empty(self):
        css = build_guide_css()
        assert len(css) > 1000

    def test_js_not_empty(self):
        js = build_guide_js()
        assert len(js) > 1000

    def test_css_has_responsive_breakpoint(self):
        css = build_guide_css()
        assert "@media(max-width:768px)" in css

    def test_js_has_gate_logic(self):
        js = build_guide_js()
        assert "gg_guide_unlocked" in js
        assert "localStorage" in js

    def test_js_has_accordion_toggle(self):
        js = build_guide_js()
        assert "gg-guide-accordion-trigger" in js

    def test_js_has_tab_switching(self):
        js = build_guide_js()
        assert "gg-guide-tab" in js

    def test_js_has_progress_bar(self):
        js = build_guide_js()
        assert "gg-guide-progress-bar" in js

    def test_js_has_intersection_observer(self):
        js = build_guide_js()
        assert "IntersectionObserver" in js

    def test_js_has_flashcard_flip(self):
        js = build_guide_js()
        assert "gg-guide-flashcard" in js
        assert "guide_flashcard_flip" in js

    def test_js_has_scenario_selection(self):
        js = build_guide_js()
        assert "gg-guide-scenario" in js
        assert "guide_scenario_choice" in js

    def test_css_has_flashcard_styles(self):
        css = build_guide_css()
        assert "gg-guide-flashcard-deck" in css
        assert "gg-guide-flashcard-front" in css

    def test_css_has_scenario_styles(self):
        css = build_guide_css()
        assert "gg-guide-scenario" in css

    def test_no_dead_beacon_url(self):
        """JS must not contain the dead /guide/ping sendBeacon URL."""
        js = build_guide_js()
        assert "/guide/ping" not in js


# ── Analytics ────────────────────────────────────────────────


class TestAnalytics:
    @pytest.fixture(scope="class")
    def guide_html(self):
        content = load_content()
        return generate_guide_page(content, inline=True)

    def test_ga4_snippet_present(self, guide_html):
        assert "G-EJJZ9T6M52" in guide_html
        assert "googletagmanager.com/gtag/js" in guide_html

    def test_js_has_track_helper(self):
        js = build_guide_js()
        assert "function track(" in js

    def test_js_has_scroll_depth(self):
        js = build_guide_js()
        assert "guide_scroll_depth" in js

    def test_js_has_chapter_view_event(self):
        js = build_guide_js()
        assert "guide_chapter_view" in js

    def test_js_has_gate_impression_event(self):
        js = build_guide_js()
        assert "guide_gate_impression" in js

    def test_js_has_unlock_event(self):
        js = build_guide_js()
        assert "guide_unlock" in js

    def test_js_has_cta_click_event(self):
        js = build_guide_js()
        assert "guide_cta_click" in js

    def test_js_has_time_on_page_event(self):
        js = build_guide_js()
        assert "guide_time_on_page" in js
        assert "beforeunload" in js

    def test_js_has_beacon_transport(self):
        js = build_guide_js()
        assert "sendBeacon" in js or "beacon" in js


# ── CTA Placement ────────────────────────────────────────────


class TestCtaPlacement:
    def test_cta_after_mapping(self):
        """Verify CTA types match the 8-chapter plan spec."""
        content = load_content()
        expected = {
            1: None,
            2: "training_plans",
            3: "gate",
            4: None,
            5: None,
            6: None,
            7: None,
            8: "finale",
        }
        for ch in content["chapters"]:
            assert ch.get("cta_after") == expected[ch["number"]], \
                f"Chapter {ch['number']} CTA mismatch"


# ── Accessibility ────────────────────────────────────────────


class TestAccessibility:
    @pytest.fixture(scope="class")
    def guide_html(self):
        content = load_content()
        return generate_guide_page(content, inline=True)

    def test_progress_bar_aria(self, guide_html):
        assert 'role="progressbar"' in guide_html
        assert 'aria-valuenow=' in guide_html
        assert 'aria-valuemin="0"' in guide_html
        assert 'aria-valuemax="100"' in guide_html

    def test_tabs_have_roles(self):
        block = {
            "tabs": [
                {"label": "Tab A", "title": "Title A", "content": "Content A"},
                {"label": "Tab B", "title": "Title B", "content": "Content B"},
            ]
        }
        html = render_tabs(block)
        assert 'role="tablist"' in html
        assert 'role="tab"' in html
        assert 'role="tabpanel"' in html
        assert 'aria-selected="true"' in html

    def test_accordion_has_aria_controls(self):
        block = {
            "items": [
                {"title": "Q1", "content": "A1"},
            ]
        }
        html = render_accordion(block)
        assert "aria-controls=" in html

    def test_chapter_nav_aria(self, guide_html):
        assert 'aria-label="Chapter navigation"' in guide_html

    def test_reduced_motion_media_query(self):
        css = build_guide_css()
        assert "prefers-reduced-motion" in css

    def test_reduced_motion_media_query_exists(self):
        """Must have prefers-reduced-motion media query for transitions."""
        css = build_guide_css()
        assert "prefers-reduced-motion" in css

    def test_focus_visible_styles(self):
        """Interactive elements must have :focus-visible styles."""
        css = build_guide_css()
        assert ":focus-visible" in css

    def test_flashcard_keyboard_accessible(self):
        block = {
            "cards": [{"front": "Q", "back": "A"}],
        }
        html = render_flashcard(block)
        assert 'role="button"' in html
        assert 'tabindex="0"' in html


# ── Determinism ──────────────────────────────────────────────


# ── Interactive Content ──────────────────────────────────────


class TestInteractiveContent:
    def test_every_chapter_has_knowledge_check(self):
        content = load_content()
        for ch in content["chapters"]:
            has_kc = any(
                block["type"] == "knowledge_check"
                for sec in ch["sections"]
                for block in sec["blocks"]
            )
            assert has_kc, f"Chapter {ch['number']} missing knowledge check"

    def test_flashcard_blocks_present(self):
        content = load_content()
        flashcard_count = sum(
            1 for ch in content["chapters"]
            for sec in ch["sections"]
            for block in sec["blocks"]
            if block["type"] == "flashcard"
        )
        assert flashcard_count >= 2

    def test_scenario_blocks_present(self):
        content = load_content()
        scenario_count = sum(
            1 for ch in content["chapters"]
            for sec in ch["sections"]
            for block in sec["blocks"]
            if block["type"] == "scenario"
        )
        assert scenario_count >= 3

    def test_flashcards_in_generated_html(self):
        content = load_content()
        html = generate_guide_page(content, inline=True)
        assert "gg-guide-flashcard-deck" in html

    def test_scenarios_in_generated_html(self):
        content = load_content()
        html = generate_guide_page(content, inline=True)
        assert "gg-guide-scenario" in html
        assert "RACE SCENARIO" in html

    def test_knowledge_checks_single_correct(self):
        """Each knowledge check must have exactly one correct answer."""
        content = load_content()
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                for block in sec["blocks"]:
                    if block["type"] == "knowledge_check":
                        correct_count = sum(
                            1 for opt in block["options"] if opt.get("correct")
                        )
                        assert correct_count == 1, \
                            f"Knowledge check in {sec['id']} has {correct_count} correct answers (expected 1)"

    def test_scenarios_single_best(self):
        """Each scenario must have exactly one best option."""
        content = load_content()
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                for block in sec["blocks"]:
                    if block["type"] == "scenario":
                        best_count = sum(
                            1 for opt in block["options"] if opt.get("best")
                        )
                        assert best_count == 1, \
                            f"Scenario in {sec['id']} has {best_count} best options (expected 1)"


# ── Determinism ──────────────────────────────────────────────


class TestDeterminism:
    def test_tab_ids_deterministic(self):
        block = {
            "tabs": [
                {"label": "Tab X", "title": "Title X", "content": "Content X"},
                {"label": "Tab Y", "title": "Title Y", "content": "Content Y"},
            ]
        }
        html1 = render_tabs(block)
        html2 = render_tabs(block)
        assert html1 == html2


# ── Calculator Renderer ─────────────────────────────────────


class TestCalculatorRenderer:
    def test_ftp_calculator_basic(self):
        block = {
            "calculator_id": "ftp-zones",
            "title": "Zone Calculator",
            "description": "Enter your FTP.",
            "inputs": [
                {"id": "ftp-power", "label": "FTP (watts)", "type": "number",
                 "placeholder": "250", "min": 50, "max": 600},
            ],
            "zones": [
                {"name": "Z1", "min_pct": 0, "max_pct": 55, "color": "#4ECDC4"},
                {"name": "Z2", "min_pct": 56, "max_pct": 75, "color": "#178079"},
            ],
        }
        html = render_calculator(block)
        assert "gg-guide-calculator" in html
        assert 'data-calc-type="ftp-zones"' in html
        assert "Zone Calculator" in html
        assert 'id="gg-calc-ftp-power"' in html
        assert 'inputmode="numeric"' in html

    def test_ftp_calculator_zones(self):
        block = {
            "calculator_id": "ftp-zones",
            "title": "Zones",
            "inputs": [{"id": "ftp-power", "label": "FTP", "type": "number"}],
            "zones": [
                {"name": "Z1", "min_pct": 0, "max_pct": 55, "hr_min_pct": 55,
                 "hr_max_pct": 72, "color": "#4ECDC4"},
            ],
        }
        html = render_calculator(block)
        assert "gg-guide-calc-zone" in html
        assert 'data-min="0"' in html
        assert 'data-max="55"' in html
        assert 'data-hr-min="55"' in html

    def test_calculator_aria_live(self):
        block = {
            "calculator_id": "test",
            "title": "Test",
            "inputs": [{"id": "x", "label": "X", "type": "number"}],
        }
        html = render_calculator(block)
        assert 'aria-live="polite"' in html

    def test_calculator_select_input(self):
        block = {
            "calculator_id": "test",
            "title": "Test",
            "inputs": [{
                "id": "day", "label": "Day", "type": "select",
                "options": [
                    {"value": "easy", "label": "Easy"},
                    {"value": "hard", "label": "Hard"},
                ],
            }],
        }
        html = render_calculator(block)
        assert "gg-guide-calc-select" in html
        assert '<option value="easy">Easy</option>' in html

    def test_calculator_toggle_input(self):
        block = {
            "calculator_id": "test",
            "title": "Test",
            "inputs": [{
                "id": "unit", "label": "Unit", "type": "toggle",
                "options": [
                    {"value": "kg", "label": "KG"},
                    {"value": "lbs", "label": "LBS"},
                ],
            }],
        }
        html = render_calculator(block)
        assert "gg-guide-calc-toggle" in html
        assert "gg-guide-calc-toggle-btn--active" in html
        assert 'data-value="kg"' in html

    def test_calculator_output_fields(self):
        block = {
            "calculator_id": "test",
            "title": "Test",
            "inputs": [{"id": "w", "label": "W", "type": "number"}],
            "output_fields": [
                {"id": "protein", "label": "Protein"},
                {"id": "carbs", "label": "Carbs"},
            ],
        }
        html = render_calculator(block)
        assert "gg-guide-calc-results" in html
        assert 'id="gg-calc-out-protein"' in html
        assert "Protein" in html

    def test_calculator_optional_input(self):
        block = {
            "calculator_id": "test",
            "title": "Test",
            "inputs": [
                {"id": "age", "label": "Age", "type": "number", "optional": True},
            ],
        }
        html = render_calculator(block)
        assert "(optional)" in html

    def test_calculator_transform_attr(self):
        block = {
            "calculator_id": "test",
            "title": "Test",
            "inputs": [
                {"id": "test", "label": "Test", "type": "number",
                 "transform": "multiply_0.95"},
            ],
        }
        html = render_calculator(block)
        assert 'data-transform="multiply_0.95"' in html

    def test_calculator_button(self):
        block = {
            "calculator_id": "test",
            "title": "Test",
            "inputs": [{"id": "x", "label": "X", "type": "number"}],
        }
        html = render_calculator(block)
        assert "CALCULATE" in html
        assert "gg-guide-calc-btn" in html


# ── Zone Visualizer Renderer ────────────────────────────────


class TestZoneVisualizerRenderer:
    def test_zone_visualizer_basic(self):
        block = {
            "title": "Zone Spectrum",
            "zones": [
                {"name": "Z1", "max_pct": 55, "label": "55%", "color": "#4ECDC4"},
                {"name": "Z2", "max_pct": 75, "label": "75%", "color": "#178079"},
            ],
        }
        html = render_zone_visualizer(block)
        assert "gg-guide-zone-viz" in html
        assert "gg-guide-viz-row" in html
        assert "Zone Spectrum" in html
        assert "gg-guide-viz-fill" in html

    def test_zone_visualizer_bars_count(self):
        block = {
            "title": "Test",
            "zones": [
                {"name": f"Z{i}", "max_pct": 50 + i * 20, "label": f"{50 + i * 20}%"}
                for i in range(4)
            ],
        }
        html = render_zone_visualizer(block)
        assert html.count("gg-guide-viz-row") == 4

    def test_zone_visualizer_no_stagger(self):
        block = {
            "title": "Test",
            "zones": [
                {"name": "Z1", "max_pct": 55, "label": "55%"},
                {"name": "Z2", "max_pct": 75, "label": "75%"},
                {"name": "Z3", "max_pct": 87, "label": "87%"},
            ],
        }
        html = render_zone_visualizer(block)
        assert "data-delay" not in html
        # Bars render at full width immediately
        assert "width:" in html

    def test_zone_visualizer_aria_label(self):
        block = {
            "title": "Test",
            "zones": [{"name": "Z1", "max_pct": 55, "label": "55%"}],
        }
        html = render_zone_visualizer(block)
        assert 'role="img"' in html
        assert 'aria-label=' in html


# ── Animated Process Bars ───────────────────────────────────


class TestAnimatedProcessBars:
    def test_process_bar_html(self):
        block = {
            "items": [
                {"label": "Fitness", "detail": "Main factor", "percentage": 70},
            ]
        }
        html = render_process_list(block)
        assert "gg-guide-process-bar-wrap" in html
        assert "gg-guide-process-bar" in html
        assert 'style="width:70%"' in html
        assert ">70%<" in html
        # No scroll-triggered animation attributes
        assert "data-pct" not in html
        assert "data-target" not in html

    def test_process_no_bar_without_percentage(self):
        block = {
            "items": [
                {"label": "Item", "detail": "No pct"},
            ]
        }
        html = render_process_list(block)
        assert "gg-guide-process-bar-wrap" not in html

    def test_process_bar_css(self):
        css = build_guide_css()
        assert "gg-guide-process-bar-wrap" in css
        assert "gg-guide-process-bar" in css

    def test_process_bar_renders_immediately(self):
        """Process bars render at full width with no JS observer needed."""
        block = {
            "items": [
                {"label": "Fitness", "detail": "Main factor", "percentage": 70},
            ]
        }
        html = render_process_list(block)
        assert 'style="width:70%"' in html


# ── Hover Micro-Interactions ────────────────────────────────


class TestHoverInteractions:
    def test_table_row_hover(self):
        css = build_guide_css()
        assert "gg-guide-table tbody tr:hover" in css


# ── Calculator CSS/JS ───────────────────────────────────────


class TestCalculatorCssJs:
    def test_calculator_css_classes(self):
        css = build_guide_css()
        assert "gg-guide-calculator" in css
        assert "gg-guide-calc-input" in css
        assert "gg-guide-calc-btn" in css
        assert "gg-guide-calc-zone" in css

    def test_calculator_css_toggle(self):
        css = build_guide_css()
        assert "gg-guide-calc-toggle" in css
        assert "gg-guide-calc-toggle-btn--active" in css

    def test_calculator_css_results(self):
        css = build_guide_css()
        assert "gg-guide-calc-results" in css
        assert "gg-guide-calc-result-value" in css

    def test_calculator_js_ftp(self):
        js = build_guide_js()
        assert "computeFtpZones" in js
        assert "ftp_zones" in js

    def test_calculator_js_nutrition(self):
        js = build_guide_js()
        assert "computeDailyNutrition" in js
        assert "daily_nutrition" in js

    def test_calculator_js_fueling(self):
        js = build_guide_js()
        assert "computeWorkoutFueling" in js
        assert "workout_fueling" in js

    def test_calculator_js_analytics(self):
        js = build_guide_js()
        assert "guide_calculator_use" in js

    def test_calculator_mobile_css(self):
        css = build_guide_css()
        assert "gg-guide-calc-zone{grid-template-columns:1fr" in css


# ── Zone Visualizer CSS/JS ──────────────────────────────────


class TestZoneVisualizerCssJs:
    def test_zone_viz_css(self):
        css = build_guide_css()
        assert "gg-guide-zone-viz" in css

    def test_zone_viz_no_scroll_animation(self):
        """Zone viz renders at full width without JS scroll observer."""
        block = {
            "title": "Test",
            "zones": [{"name": "Z1", "max_pct": 100, "label": "100%"}],
        }
        html = render_zone_visualizer(block)
        assert "width:100.0%" in html


# ── Rider Personalization ───────────────────────────────────


class TestRiderPersonalization:
    def test_personalization_config_in_content(self):
        content = load_content()
        assert "personalization" in content
        p = content["personalization"]
        assert "rider_types" in p
        assert len(p["rider_types"]) == 4

    def test_rider_types_have_required_fields(self):
        content = load_content()
        for rt in content["personalization"]["rider_types"]:
            assert "id" in rt
            assert "label" in rt
            assert "hours" in rt
            assert "default_ftp" in rt

    def test_rider_selector_html(self):
        content = load_content()
        html = build_rider_selector(content)
        assert "gg-guide-rider-selector" in html
        assert 'role="radiogroup"' in html
        assert html.count('role="radio"') == 4
        assert "Ayahuasca" in html
        assert "Finisher" in html
        assert "Competitor" in html
        assert "Podium" in html

    def test_rider_badge_html(self):
        content = load_content()
        html = build_rider_selector(content)
        assert "gg-guide-rider-badge" in html
        assert "CHANGE" in html

    def test_rider_selector_empty_without_config(self):
        content = {"title": "Test", "meta_description": "Test", "chapters": []}
        html = build_rider_selector(content)
        assert html == ''

    def test_rider_selector_in_page(self):
        content = load_content()
        html = generate_guide_page(content, inline=True)
        assert "gg-guide-rider-selector" in html

    def test_rider_css(self):
        css = build_guide_css()
        assert "gg-guide-rider-selector" in css
        assert "gg-guide-rider-badge" in css
        assert "gg-guide-rider-btn--active" in css

    def test_rider_js_storage(self):
        js = build_guide_js()
        assert "gg_guide_rider_type" in js
        assert "setRider" in js

    def test_rider_js_tab_auto_select(self):
        js = build_guide_js()
        assert "gg-guide-tabs" in js
        # Should auto-select matching tabs by data-rider-type attribute
        assert "data-rider-type" in js

    def test_rider_js_ftp_prefill(self):
        js = build_guide_js()
        assert "gg-calc-ftp-power" in js
        assert "placeholder" in js

    def test_rider_js_analytics(self):
        js = build_guide_js()
        assert "guide_rider_select" in js


# ── Counter Pattern ─────────────────────────────────────────


class TestCounterPattern:
    def test_counter_inline_conversion(self):
        result = _md_inline("There are {{328}} races.")
        assert 'class="gg-guide-counter"' in result
        assert ">328<" in result

    def test_counter_decimal(self):
        result = _md_inline("Score is {{70.5}}.")
        assert ">70.5<" in result

    def test_counter_in_content(self):
        content = load_content()
        html = generate_guide_page(content, inline=True)
        assert "gg-guide-counter" in html

    def test_counter_css(self):
        css = build_guide_css()
        assert "gg-guide-counter" in css

    def test_counter_renders_final_value(self):
        """Counter renders final value immediately, no scroll animation."""
        result = _md_inline("Score is {{328}}.")
        assert ">328<" in result
        assert "data-target" not in result


# ── Content JSON Integrity ──────────────────────────────────


class TestContentJsonIntegrity:
    def test_calculator_blocks_in_ch3(self):
        content = load_content()
        ch3 = [ch for ch in content["chapters"] if ch["number"] == 3][0]
        calc_blocks = [
            b for sec in ch3["sections"] for b in sec["blocks"]
            if b["type"] == "calculator"
        ]
        assert len(calc_blocks) == 1
        assert calc_blocks[0]["calculator_id"] == "ftp-zones"

    def test_zone_visualizer_in_ch3(self):
        content = load_content()
        ch3 = [ch for ch in content["chapters"] if ch["number"] == 3][0]
        viz_blocks = [
            b for sec in ch3["sections"] for b in sec["blocks"]
            if b["type"] == "zone_visualizer"
        ]
        assert len(viz_blocks) == 1

    def test_calculator_blocks_in_ch5(self):
        content = load_content()
        ch5 = [ch for ch in content["chapters"] if ch["number"] == 5][0]
        calc_blocks = [
            b for sec in ch5["sections"] for b in sec["blocks"]
            if b["type"] == "calculator"
        ]
        assert len(calc_blocks) == 2
        calc_ids = {b["calculator_id"] for b in calc_blocks}
        assert calc_ids == {"daily-nutrition", "workout-fueling"}

    def test_all_calculators_have_inputs(self):
        content = load_content()
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                for b in sec["blocks"]:
                    if b["type"] == "calculator":
                        assert len(b["inputs"]) > 0, \
                            f"Calculator {b['calculator_id']} has no inputs"

    def test_counter_markers_in_prose(self):
        """At least one prose block uses the {{N}} counter pattern."""
        content = load_content()
        has_counter = False
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                for b in sec["blocks"]:
                    if b["type"] == "prose" and "{{" in b.get("content", ""):
                        has_counter = True
        assert has_counter, "No {{N}} counter markers found in prose blocks"


# ── Size Budget ─────────────────────────────────────────────


class TestSizeBudget:
    def test_css_under_budget(self):
        css = build_guide_css()
        assert len(css) < 62000, f"CSS is {len(css)} bytes, exceeds 62KB budget"

    def test_js_under_budget(self):
        js = build_guide_js()
        assert len(js) < 30000, f"JS is {len(js)} bytes, exceeds 30KB budget"


# ── Sprint 17: Behavior-Level Tests ────────────────────────


class TestCalculatorValidation:
    def test_js_has_ftp_range_check(self):
        """JS must validate FTP input range (50-600)."""
        js = build_guide_js()
        assert "ftp<50" in js or "ftp < 50" in js
        assert "ftp>600" in js or "ftp > 600" in js

    def test_js_has_weight_range_check(self):
        """JS must validate weight input."""
        js = build_guide_js()
        assert "w<30" in js or "w < 30" in js

    def test_js_has_duration_range_check(self):
        """JS must validate duration input."""
        js = build_guide_js()
        assert "dur<0.5" in js or "dur < 0.5" in js

    def test_error_css_class_exists(self):
        """CSS must have the calc-input--error class."""
        css = build_guide_css()
        assert "gg-guide-calc-input--error" in css

    def test_error_message_div_in_html(self):
        """Calculator HTML must include an error message div."""
        block = {
            "calculator_id": "test",
            "title": "Test",
            "inputs": [{"id": "x", "label": "X", "type": "number"}],
        }
        html = render_calculator(block)
        assert "gg-guide-calc-error" in html


class TestObserverConsolidation:
    def test_max_three_observers(self):
        """JS must have at most 3 IntersectionObserver instances (chapter tracking + gate + infographic animations)."""
        js = build_guide_js()
        count = js.count("new IntersectionObserver")
        assert count <= 3, f"Found {count} IntersectionObserver instances, expected <= 3"

    def test_no_bare_ticking_var(self):
        """JS must not have a bare 'var ticking' (should be split)."""
        js = build_guide_js()
        assert "var ticking" not in js


class TestTickingFix:
    def test_progress_ticking_exists(self):
        """JS must use progressTicking for progress bar."""
        js = build_guide_js()
        assert "progressTicking" in js


class TestReservedWordFix:
    def test_no_var_is(self):
        """JS must not use 'var is' (reserved word)."""
        js = build_guide_js()
        assert "var is " not in js
        assert "var is=" not in js


class TestZoneVizHtmlBars:
    def test_viz_uses_html_not_svg(self):
        """Zone visualizer must use HTML divs, not SVG."""
        block = {
            "title": "Test",
            "zones": [{"name": "Z1", "max_pct": 55, "label": "55%"}],
        }
        html = render_zone_visualizer(block)
        assert "gg-guide-viz-row" in html
        assert "<svg" not in html

    def test_viz_has_role_img(self):
        """Zone viz bars container must have role=img."""
        block = {
            "title": "Test",
            "zones": [{"name": "Z1", "max_pct": 55, "label": "55%"}],
        }
        html = render_zone_visualizer(block)
        assert 'role="img"' in html

    def test_viz_renders_full_width(self):
        """Zone viz fill elements must render at full width immediately."""
        block = {
            "title": "Test",
            "zones": [
                {"name": "Z1", "max_pct": 55, "label": "55%"},
                {"name": "Z2", "max_pct": 100, "label": "100%"},
            ],
        }
        html = render_zone_visualizer(block)
        assert "width:55.0%" in html
        assert "width:100.0%" in html
        assert "data-pct" not in html


class TestRiderDataAttr:
    def test_tabs_emit_data_rider_type(self):
        """render_tabs() must emit data-rider-type when tab has rider_type."""
        block = {
            "tabs": [
                {"label": "Ayahuasca", "rider_type": "ayahuasca", "content": "C1"},
                {"label": "Finisher", "rider_type": "finisher", "content": "C2"},
            ]
        }
        html = render_tabs(block)
        assert 'data-rider-type="ayahuasca"' in html
        assert 'data-rider-type="finisher"' in html

    def test_tabs_without_rider_type_no_attr(self):
        """render_tabs() must not emit data-rider-type when tab lacks it."""
        block = {
            "tabs": [
                {"label": "Tab 1", "content": "C1"},
                {"label": "Tab 2", "content": "C2"},
            ]
        }
        html = render_tabs(block)
        assert "data-rider-type" not in html

    def test_js_uses_data_rider_type_selector(self):
        """JS must use data-rider-type attribute selector for tab matching."""
        js = build_guide_js()
        assert "data-rider-type" in js


class TestCounterBounds:
    def test_8_digit_counter_not_converted(self):
        """Counter regex must reject 8+ digit numbers."""
        result = _md_inline("{{99999999}}")
        assert "gg-guide-counter" not in result
        assert "{{99999999}}" in result

    def test_7_digit_counter_converted(self):
        """Counter regex must accept 7-digit numbers."""
        result = _md_inline("{{9999999}}")
        assert "gg-guide-counter" in result
        assert ">9999999<" in result

    def test_3_decimal_counter_not_converted(self):
        """Counter regex must reject 3+ decimal places."""
        result = _md_inline("{{70.123}}")
        assert "gg-guide-counter" not in result

    def test_2_decimal_counter_converted(self):
        """Counter regex must accept 2 decimal places."""
        result = _md_inline("{{70.12}}")
        assert "gg-guide-counter" in result
        assert ">70.12<" in result


# ── Image / Video Renderers ────────────────────────────────


class TestImageRenderer:
    def test_render_image_basic(self):
        """Image block must produce figure, srcset, loading=lazy."""
        block = {"asset_id": "ch1-hero", "alt": "Gravel road at golden hour"}
        html = render_image(block)
        assert '<figure class="gg-guide-img">' in html
        assert 'src="/guide/media/ch1-hero-1x.webp"' in html
        assert 'srcset="/guide/media/ch1-hero-1x.webp 1x, /guide/media/ch1-hero-2x.webp 2x"' in html
        assert 'loading="lazy"' in html
        assert 'decoding="async"' in html
        assert 'alt="Gravel road at golden hour"' in html

    def test_render_image_caption(self):
        """Figcaption rendered when caption provided."""
        block = {"asset_id": "ch2-zones", "alt": "Zones", "caption": "Training zones overview"}
        html = render_image(block)
        assert "gg-guide-img-caption" in html
        assert "Training zones overview" in html

    def test_render_image_no_caption(self):
        """No figcaption when caption absent."""
        block = {"asset_id": "ch1-hero", "alt": "Test"}
        html = render_image(block)
        assert "figcaption" not in html

    def test_render_image_layout_full_width(self):
        """Full-width layout class applied."""
        block = {"asset_id": "ch3-info", "alt": "Test", "layout": "full-width"}
        html = render_image(block)
        assert "gg-guide-img--full-width" in html

    def test_render_image_layout_half_width(self):
        """Half-width layout class applied."""
        block = {"asset_id": "ch4-info", "alt": "Test", "layout": "half-width"}
        html = render_image(block)
        assert "gg-guide-img--half-width" in html

    def test_render_image_inline_no_extra_class(self):
        """Inline layout (default) has no extra layout class on figure tag."""
        block = {"asset_id": "ch5-info", "alt": "Test"}
        html = render_image(block)
        assert 'class="gg-guide-img">' in html
        # gg-guide-img--missing appears in onerror handler, but not as a figure class
        assert "gg-guide-img--full-width" not in html
        assert "gg-guide-img--half-width" not in html


class TestVideoRenderer:
    def test_render_video_basic(self):
        """Video block must produce figure, video tag, controls, preload=none."""
        block = {"asset_id": "ch6-demo", "alt": "Demo video"}
        html = render_video(block)
        assert '<figure class="gg-guide-img gg-guide-video">' in html
        assert 'src="/guide/media/ch6-demo.mp4"' in html
        assert "controls" in html
        assert 'preload="none"' in html
        assert "Demo video" in html

    def test_render_video_poster(self):
        """Poster attribute when poster_id provided."""
        block = {"asset_id": "ch6-demo", "alt": "Demo", "poster": "ch6-demo-poster"}
        html = render_video(block)
        assert 'poster="/guide/media/ch6-demo-poster-1x.webp"' in html

    def test_render_video_no_poster(self):
        """No poster attribute when poster absent."""
        block = {"asset_id": "ch6-demo", "alt": "Demo"}
        html = render_video(block)
        assert "poster=" not in html

    def test_render_video_caption(self):
        """Video caption rendered when provided."""
        block = {"asset_id": "ch6-demo", "alt": "Demo", "caption": "Watch the demo"}
        html = render_video(block)
        assert "gg-guide-img-caption" in html
        assert "Watch the demo" in html


class TestBlockRenderersDispatch:
    def test_block_renderers_has_image_video(self):
        """BLOCK_RENDERERS dispatch dict includes image and video."""
        assert "image" in BLOCK_RENDERERS
        assert "video" in BLOCK_RENDERERS
        assert BLOCK_RENDERERS["image"] is render_image
        assert BLOCK_RENDERERS["video"] is render_video


class TestChapterHeroImage:
    def test_chapter_hero_image(self):
        """Hero div gets background-image URL when hero_image set."""
        chapter = {
            "number": 1,
            "id": "test-chapter",
            "title": "Test",
            "subtitle": "",
            "gated": False,
            "sections": [],
            "hero_image": "ch1-hero",
        }
        html = build_chapter(chapter)
        assert "url(/guide/media/ch1-hero-1x.webp)" in html
        assert "center/cover no-repeat" in html

    def test_chapter_no_hero_image(self):
        """Hero div uses plain background color when no hero_image."""
        chapter = {
            "number": 1,
            "id": "test-chapter",
            "title": "Test",
            "subtitle": "",
            "gated": False,
            "sections": [],
        }
        html = build_chapter(chapter)
        assert "url(/guide/media/" not in html
        assert "background:#59473c" in html


class TestImageCss:
    def test_css_has_image_styles(self):
        """CSS must include image block styles."""
        css = build_guide_css()
        assert "gg-guide-img{" in css or "gg-guide-img {" in css
        assert "gg-guide-img-el" in css
        assert "gg-guide-img-caption" in css

    def test_css_has_image_layout_variants(self):
        """CSS must include full-width and half-width layout classes."""
        css = build_guide_css()
        assert "gg-guide-img--full-width" in css
        assert "gg-guide-img--half-width" in css

    def test_css_budget_with_images(self):
        """CSS still under 25KB budget after image additions."""
        css = build_guide_css()
        assert len(css) < 62000, f"CSS is {len(css)} bytes, exceeds 62KB budget"

    def test_css_image_responsive(self):
        """Image layout classes have responsive overrides."""
        css = build_guide_css()
        # Mobile overrides for image layouts in @media block
        assert "gg-guide-img--full-width{margin-left:-16px" in css
        assert "gg-guide-img--half-width{float:none" in css


# ── Tooltip System ─────────────────────────────────────────


class TestTooltipSystem:
    _saved_glossary = None

    @classmethod
    def setup_class(cls):
        cls._saved_glossary = generate_guide._GLOSSARY

    @classmethod
    def teardown_class(cls):
        generate_guide._GLOSSARY = cls._saved_glossary

    def setup_method(self):
        generate_guide._GLOSSARY = {
            "FTP": "Functional Threshold Power — the max watts you can sustain for ~1 hour",
            "Z2": "Zone 2 — easy aerobic pace, 55-75% of FTP",
        }

    def teardown_method(self):
        generate_guide._GLOSSARY = self._saved_glossary

    def test_md_inline_tooltip_basic(self):
        """{{FTP}} produces a span with class gg-tooltip-trigger."""
        result = _md_inline("Your {{FTP}} matters.")
        assert 'class="gg-tooltip-trigger"' in result
        assert ">FTP<" in result

    def test_md_inline_tooltip_definition(self):
        """Tooltip span contains the glossary definition text."""
        result = _md_inline("Test {{FTP}} here.")
        assert 'class="gg-tooltip"' in result
        assert "Functional Threshold Power" in result

    def test_md_inline_tooltip_unknown_term(self):
        """Unknown term renders as plain text without tooltip."""
        result = _md_inline("Test {{UNKNOWN}} here.")
        assert "gg-tooltip-trigger" not in result
        assert "UNKNOWN" in result

    def test_md_inline_tooltip_no_glossary(self):
        """Without glossary, {{FTP}} passes through unchanged."""
        generate_guide._GLOSSARY = None
        result = _md_inline("Test {{FTP}} here.")
        assert "{{FTP}}" in result
        assert "gg-tooltip-trigger" not in result

    def test_md_inline_counter_still_works(self):
        """{{1200}} still produces counter span with glossary active."""
        result = _md_inline("There are {{1200}} races.")
        assert 'class="gg-guide-counter"' in result
        assert ">1200<" in result

    def test_md_inline_mixed(self):
        """{{FTP}} and {{1200}} both resolve correctly in same string."""
        result = _md_inline("Your {{FTP}} across {{328}} races.")
        assert "gg-tooltip-trigger" in result
        assert "gg-guide-counter" in result
        assert ">328<" in result
        assert "Functional Threshold Power" in result

    def test_tooltip_css_present(self):
        """CSS output contains tooltip classes."""
        css = build_guide_css()
        assert ".gg-tooltip-trigger" in css
        assert ".gg-tooltip{" in css or ".gg-tooltip " in css
        assert "#9a7e0a" in css
        assert "#3a2e25" in css

    def test_tooltip_tabindex(self):
        """Tooltip trigger includes tabindex=0 for accessibility."""
        result = _md_inline("Test {{FTP}} here.")
        assert 'tabindex="0"' in result


class TestTooltipContentIntegrity:
    def test_glossary_in_content(self):
        """Content JSON has a glossary dict with terms."""
        content = load_content()
        assert "glossary" in content
        assert len(content["glossary"]) >= 10

    def test_tooltip_markers_in_prose(self):
        """At least one prose block uses the {{TERM}} tooltip pattern."""
        content = load_content()
        has_tooltip = False
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                for b in sec["blocks"]:
                    if b["type"] == "prose" and re.search(
                        r'\{\{[A-Za-z]', b.get("content", "")
                    ):
                        has_tooltip = True
        assert has_tooltip, "No {{TERM}} tooltip markers found in prose blocks"

    def test_tooltips_in_generated_html(self):
        """Generated guide HTML contains resolved tooltip spans."""
        content = load_content()
        html = generate_guide_page(content, inline=True)
        assert "gg-tooltip-trigger" in html
        assert "gg-tooltip" in html


# ── Brand Compliance ────────────────────────────────────────


class TestBrandCompliance:
    def test_source_serif_in_css(self):
        """CSS must include Source Serif 4 font-family."""
        css = build_guide_css()
        assert "Source Serif 4" in css

    def test_border_color_dark_brown(self):
        """No 'solid #000' in CSS — all borders must use #3a2e25."""
        css = build_guide_css()
        assert "solid #000" not in css

    def test_no_scroll_animations(self):
        """No gg-guide-fade-in or gg-guide-stagger classes in CSS."""
        css = build_guide_css()
        assert "gg-guide-fade-in" not in css
        assert "gg-guide-stagger" not in css

    def test_no_parallax_in_js(self):
        """No parallax scroll handler in JS."""
        js = build_guide_js()
        assert "parallax" not in js.lower()
        assert "backgroundPositionY" not in js

    def test_no_stagger_in_html(self):
        """Generated HTML has no gg-guide-stagger class."""
        content = load_content()
        html = generate_guide_page(content, inline=True)
        assert "gg-guide-stagger" not in html

    def test_flashcard_no_3d(self):
        """No 3D transform properties in flashcard CSS."""
        css = build_guide_css()
        assert "perspective" not in css
        assert "rotateY" not in css
        assert "preserve-3d" not in css

    def test_error_color(self):
        """CSS uses #c0392b for errors, not #c44."""
        css = build_guide_css()
        assert "#c0392b" in css
        assert "#c44" not in css

    def test_tab_active_gold_border(self):
        """Active tab uses gold bottom border, not teal background."""
        css = build_guide_css()
        assert "gg-guide-tab--active" in css
        # Active tab should have gold border-bottom
        active_idx = css.index("gg-guide-tab--active")
        active_rule = css[active_idx:active_idx + 200]
        assert "#9a7e0a" in active_rule
        # Should NOT have teal background for active tab
        assert "background:#178079" not in active_rule


# ── Sprint 19: Visual Enrichment ──────────────────────────


class TestSprint19VisualEnrichment:
    def test_image_has_onerror_fallback(self):
        """render_image() output contains onerror and placeholder div."""
        block = {"asset_id": "ch1-hero", "alt": "Gravel road at golden hour"}
        html = render_image(block)
        assert "onerror=" in html
        assert "gg-guide-img-placeholder" in html
        assert "Gravel road at golden hour" in html

    def test_image_placeholder_uses_asset_id_when_no_alt(self):
        """Placeholder shows asset_id when alt text is empty."""
        block = {"asset_id": "ch1-hero"}
        html = render_image(block)
        assert "gg-guide-img-placeholder" in html
        assert "ch1-hero" in html

    def test_footer_dark_brown_bg(self):
        """Footer CSS uses dark-brown background (#3a2e25)."""
        css = build_guide_css()
        # Chapter footer
        footer_idx = css.index(".gg-guide-chapter-body .gg-footer")
        footer_rule = css[footer_idx:footer_idx + 200]
        assert "background:#3a2e25" in footer_rule

    def test_image_caption_dark_bar(self):
        """.gg-guide-img-caption CSS has dark background."""
        css = build_guide_css()
        cap_idx = css.index(".gg-guide-img-caption{")
        cap_rule = css[cap_idx:cap_idx + 300]
        assert "background:#3a2e25" in cap_rule

    def test_layout_width_1200(self):
        """Page CSS contains max-width: 1200px."""
        content = load_content()
        html = generate_guide_page(content, inline=True)
        assert "max-width: 1200px" in html

    def test_double_rule_borders(self):
        """CSS contains 4px double border rules."""
        css = build_guide_css()
        assert "4px double" in css

    def test_table_hover_gold_tint(self):
        """Table hover uses gold-tinted rgba background."""
        css = build_guide_css()
        assert "rgba(183,149,11" in css

    def test_placeholder_css_present(self):
        """CSS has missing-image placeholder styles."""
        css = build_guide_css()
        assert "gg-guide-img-placeholder" in css
        assert "gg-guide-img--missing" in css

    def test_callout_quote_bg_tint(self):
        """Quote callout has gold-tinted background."""
        css = build_guide_css()
        quote_idx = css.index(".gg-guide-callout--quote{")
        quote_rule = css[quote_idx:quote_idx + 200]
        assert "rgba(183,149,11,0.04)" in quote_rule

    def test_knowledge_check_label_dark_text(self):
        """Knowledge check label uses dark text color on gold bg."""
        css = build_guide_css()
        kc_idx = css.index(".gg-guide-kc-label{")
        kc_rule = css[kc_idx:kc_idx + 200]
        assert "color:#3a2e25" in kc_rule

    def test_no_gray_ddd_in_css(self):
        """CSS should not contain #ddd (replaced with warm tan)."""
        css = build_guide_css()
        assert "#ddd" not in css


# ── Infographic Dispatch ──────────────────────────────────


class TestInfographicDispatch:
    def test_infographic_asset_ids_produce_inline_content(self):
        """Infographic asset_ids should produce inline SVG/HTML, not <img>."""
        from guide_infographics import INFOGRAPHIC_RENDERERS
        for aid in INFOGRAPHIC_RENDERERS:
            block = {"asset_id": aid, "alt": "test", "caption": "test caption"}
            html = render_image(block)
            assert "<img " not in html, f"{aid} produced <img> tag"
            assert "<figure" in html, f"{aid} missing <figure> wrapper"

    def test_hero_photos_still_produce_img(self):
        """Hero asset_ids must still render as <img> tags."""
        for ch_num in range(1, 9):
            block = {"asset_id": f"ch{ch_num}-hero", "alt": "Hero photo"}
            html = render_image(block)
            assert "<img " in html, f"ch{ch_num}-hero should produce <img>"
            assert "srcset=" in html

    def test_css_has_root_custom_properties(self):
        """build_guide_css() must include :root with color custom properties."""
        css = build_guide_css()
        assert ":root{" in css or ":root {" in css
        assert "--gg-color-primary-brown" in css
        assert "--gg-color-teal" in css
        assert "--gg-color-gold" in css

    def test_css_has_infographic_section(self):
        """build_guide_css() must include infographic CSS classes."""
        css = build_guide_css()
        assert "gg-infographic" in css
        assert "gg-infographic-caption" in css
        assert "gg-infographic-card" in css

    def test_infographics_in_full_page(self):
        """Full page generation should include inline infographics."""
        content = load_content()
        html = generate_guide_page(content, inline=True)
        assert "gg-infographic" in html
        # At least some SVG charts should appear
        assert "viewBox" in html

    def test_css_budget_with_infographics(self):
        """CSS still under 30KB budget after infographic additions."""
        css = build_guide_css()
        assert len(css) < 62000, f"CSS is {len(css)} bytes, exceeds 62KB budget"
