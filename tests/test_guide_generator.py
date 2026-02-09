"""Tests for the Gravel God Training Guide generator."""
import json
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path so we can import the generator
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

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
    build_nav,
    build_hero,
    build_gate,
    build_cta_newsletter,
    build_cta_training,
    build_cta_coaching,
    build_cta_finale,
    build_jsonld,
    build_guide_css,
    build_guide_js,
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
        assert "70%" in html

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
        # Chapter 1 should NOT have gated class
        assert 'id="what-is-gravel-racing" data-chapter="1"' in guide_html

    def test_gate_overlay_present(self, guide_html):
        assert 'id="gg-guide-gate"' in guide_html
        assert "CHAPTERS 4-8 ARE LOCKED" in guide_html
        assert "Unlock the Full Guide" in guide_html

    def test_progress_bar_present(self, guide_html):
        assert 'id="gg-guide-progress"' in guide_html

    def test_chapter_nav_present(self, guide_html):
        assert 'id="gg-guide-chapnav"' in guide_html
        assert guide_html.count("gg-guide-chapnav-item") >= 8

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

    def test_nav_links(self, guide_html):
        assert "ALL RACES" in guide_html
        assert "HOW WE RATE" in guide_html
        assert "GUIDE" in guide_html

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
        assert '"@type": "Article"' in jsonld
        assert content["title"] in jsonld

    def test_breadcrumb_schema(self):
        content = load_content()
        jsonld = build_jsonld(content)
        assert '"@type": "BreadcrumbList"' in jsonld
        assert "Training Guide" in jsonld

    def test_valid_json(self):
        content = load_content()
        jsonld = build_jsonld(content)
        # Extract JSON blocks and validate
        import re
        blocks = re.findall(r'<script type="application/ld\+json">\n(.+?)\n</script>', jsonld, re.DOTALL)
        assert len(blocks) == 2
        for block in blocks:
            parsed = json.loads(block)
            assert "@context" in parsed

    def test_jsonld_has_dates(self):
        content = load_content()
        jsonld = build_jsonld(content)
        assert '"datePublished"' in jsonld
        assert '"dateModified"' in jsonld

    def test_jsonld_has_image(self):
        content = load_content()
        jsonld = build_jsonld(content)
        assert '"image"' in jsonld


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
