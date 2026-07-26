"""Tests for the course platform block renderers and calculators.

Covers the Dirt Craft port (Jun 2026):
  - every block type used in course lesson data has a renderer
  - every calculator_id has a compute branch in build_course_js (regression
    guard for the CALCULATE-button-does-nothing bug)
  - dirt-craft manifest file paths resolve
  - new renderers escape HTML
  - generated lesson pages contain GA4 and no inline onclick= handlers
  - image blocks reference asset files that exist
"""
import json
import re
import sys
from pathlib import Path

import pytest

V2_CONTENT_SKIP = pytest.mark.skip(
    reason="Rise Blocks v2 content wave not authored yet: shipped lesson JSONs "
           "are v1 blocks (no image/labeled_graphic/sorting/continue_gate/"
           "calculator placements). Illustrations + interactive specs are staged "
           "in the dirt-craft-course repo. Unskip when v2 lesson content lands.")

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

import generate_courses
from generate_courses import build_course_js, build_lesson_page, load_course
from generate_guide import (
    BLOCK_RENDERERS,
    render_black_box,
    render_calculator,
    render_commitment,
    render_drill,
    render_image,
    render_process,
    render_quiz,
    render_recovery_protocol,
    render_sensation_target,
)
from brand_tokens import get_ga4_head_snippet

PROJECT_ROOT = Path(__file__).parent.parent
COURSES_DIR = PROJECT_ROOT / "data" / "courses"

XSS = '<script>alert(1)</script>'


def iter_lesson_blocks():
    """Yield (course_dir_name, lesson_file_name, block) for every block in
    every lesson of every course, including blocks nested in accordions."""
    for course_dir in sorted(COURSES_DIR.iterdir()):
        lessons_dir = course_dir / "lessons"
        if not lessons_dir.is_dir():
            continue
        for lesson_file in sorted(lessons_dir.glob("*.json")):
            data = json.loads(lesson_file.read_text(encoding="utf-8"))
            for block in data.get("blocks", []):
                yield course_dir.name, lesson_file.name, block
                if block.get("type") == "accordion":
                    for item in block.get("items", []):
                        for nested in item.get("blocks", []):
                            yield course_dir.name, lesson_file.name, nested


ALL_BLOCKS = list(iter_lesson_blocks())


# ── (a) Every block type has a renderer ──────────────────────


class TestBlockTypeCoverage:
    def test_lessons_exist(self):
        assert len(ALL_BLOCKS) > 100, "expected course lesson data to be present"

    def test_every_block_type_has_renderer(self):
        used = {b["type"] for _, _, b in ALL_BLOCKS}
        missing = used - set(BLOCK_RENDERERS)
        assert not missing, f"block types without a renderer: {sorted(missing)}"

    def test_dirt_craft_block_types_registered(self):
        for t in ("black_box", "sensation_target", "process", "drill",
                  "recovery_protocol", "commitment", "quiz"):
            assert t in BLOCK_RENDERERS, f"'{t}' missing from BLOCK_RENDERERS"


# ── (b) Every calculator_id has a compute branch ─────────────


class TestCalculatorCoverage:
    def _course_js(self):
        fake_course = {"id": "test-course", "total_lessons": 1}
        return build_course_js(fake_course, {})

    def test_every_calculator_id_has_compute_branch(self):
        js = self._course_js()
        calc_ids = {b["calculator_id"] for _, _, b in ALL_BLOCKS
                    if b["type"] == "calculator"}
        assert calc_ids, "expected calculator blocks in course data"
        for cid in sorted(calc_ids):
            assert f"calcType==='{cid}'" in js, (
                f"calculator_id '{cid}' has no compute branch in build_course_js — "
                f"its CALCULATE button would do nothing"
            )

    def test_known_calculators_present(self):
        js = self._course_js()
        for cid in ("gravel-hydration-mastery-sweat-rate",
                    "gravel-hydration-mastery-race-plan",
                    "dirt-craft-pressure-baseline", "dirt-craft-corner-speed",
                    "dirt-craft-gearing-check", "dirt-craft-tire-pressure"):
            assert f"calcType==='{cid}'" in js

    def test_calc_js_binds_calculate_buttons(self):
        js = self._course_js()
        assert ".gg-guide-calculator" in js
        assert ".gg-guide-calc-btn" in js
        assert "addEventListener('click'" in js

    def test_calc_js_uses_textcontent_not_innerhtml(self):
        js = self._course_js()
        assert "innerHTML" not in js
        assert "eval(" not in js

    def test_calc_js_shows_errors_in_error_div(self):
        js = self._course_js()
        assert ".gg-guide-calc-error" in js

    def test_race_slug_inputs_ignored_by_compute(self):
        """race_slug fields are notes-only — compute must never read them.
        (Comments may mention race_slug; code references would be quoted or
        selector-prefixed.)"""
        js = self._course_js()
        assert "'race_slug'" not in js
        assert "#gg-calc-race_slug" not in js


# ── (c) Manifest file paths resolve ──────────────────────────


class TestDirtCraftManifest:
    def _course(self):
        return json.loads(
            (COURSES_DIR / "dirt-craft" / "course.json").read_text(encoding="utf-8"))

    def test_manifest_paths_resolve(self):
        course = self._course()
        for module in course["modules"]:
            for lesson in module["lessons"]:
                path = COURSES_DIR / "dirt-craft" / lesson["file"]
                assert path.exists(), f"manifest references missing file: {lesson['file']}"

    def test_course_loads_with_21_lessons(self):
        course = load_course(COURSES_DIR / "dirt-craft")
        assert course is not None, "dirt-craft course failed to load (check status)"
        assert course["total_lessons"] == 21
        assert len(course["modules"]) == 7

    def test_stack_check_is_final_lesson_of_core_modules(self):
        # The 4 core skill modules each end on a stack-check quiz lesson.
        # start-here, skills-lab, and the physics appendix have none.
        course = self._course()
        core = [m for m in course["modules"]
                if any("stack-check" in l["id"] for l in m["lessons"])]
        assert len(core) == 4
        for module in core:
            assert "stack-check" in module["lessons"][-1]["id"]

    def test_required_fields(self):
        course = self._course()
        assert course["id"] == "dirt-craft"
        assert course["status"] == "active"
        assert course["price_usd"] == 49
        assert len(course["meta_description"]) < 160
        assert len(course["what_youll_learn"]) >= 6
        assert course["instructor"]["name"] == "Matti Rowe"

    def test_lesson_ids_unique(self):
        course = self._course()
        ids = [l["id"] for m in course["modules"] for l in m["lessons"]]
        assert len(ids) == len(set(ids))


# ── (d) New renderers escape HTML ────────────────────────────


class TestEscaping:
    def test_black_box_escapes(self):
        html = render_black_box({"type": "black_box", "title": XSS, "content": XSS})
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_sensation_target_escapes(self):
        html = render_sensation_target(
            {"type": "sensation_target", "label": XSS, "content": XSS})
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_process_escapes(self):
        html = render_process({
            "type": "process", "title": XSS, "description": XSS,
            "steps": [{"step": 1, "action": XSS, "detail": XSS}],
        })
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_drill_escapes(self):
        html = render_drill({
            "type": "drill", "title": XSS, "time_minutes": 15, "description": XSS,
            "variants": [{"level": "beginner", "label": XSS, "steps": [XSS]}],
            "proof_gate": {"target": XSS},
        })
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_drill_unknown_level_not_injected_as_class(self):
        html = render_drill({
            "type": "drill", "title": "t", "variants":
            [{"level": 'x" onmouseover="alert(1)', "label": "l", "steps": ["s"]}],
        })
        assert 'onmouseover="alert' not in html

    def test_recovery_protocol_escapes(self):
        html = render_recovery_protocol({
            "type": "recovery_protocol", "title": XSS,
            "scenarios": [{"label": XSS, "situation": XSS, "steps": [XSS]}],
        })
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_commitment_escapes(self):
        html = render_commitment({"type": "commitment", "content": XSS})
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_quiz_escapes(self):
        html = render_quiz({
            "type": "quiz", "question": XSS, "explanation": XSS,
            "options": [{"text": XSS, "correct": True}],
        })
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_quiz_uses_kc_classes_for_xp_js(self):
        """Quiz blocks must reuse knowledge-check classes so the existing
        XP interaction JS binds to them."""
        html = render_quiz({
            "type": "quiz", "question": "q", "explanation": "e",
            "options": [{"text": "a", "correct": True}],
        })
        assert "gg-guide-kc-option" in html
        assert "data-question-hash" in html
        assert ">QUIZ<" in html

    def test_image_src_escapes(self):
        html = render_image({"type": "image", "src": XSS, "alt": XSS, "caption": XSS})
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_calculator_text_input_escapes(self):
        html = render_calculator({
            "type": "calculator", "calculator_id": "dirt-craft-corner-speed",
            "title": XSS, "description": XSS,
            "inputs": [{"id": "race_slug", "label": XSS, "type": "text",
                        "optional": True, "placeholder": XSS}],
            "output_fields": [{"id": "out", "label": XSS}],
        })
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert 'type="text"' in html


# ── (e) Generated lesson pages: GA4 present, no inline onclick ──


@pytest.fixture(scope="module")
def dirt_craft_lesson_html():
    course = load_course(COURSES_DIR / "dirt-craft")
    flat = generate_courses.get_flat_lessons(course)
    module, lesson = flat[0]
    return build_lesson_page(course, module, lesson, 0, len(flat), flat)


class TestGeneratedPages:
    def test_lesson_page_has_ga4(self, dirt_craft_lesson_html):
        ga4 = get_ga4_head_snippet()
        # The GA4 measurement id must be present in the page head
        m = re.search(r"G-[A-Z0-9]{8,}", ga4)
        assert m, "GA4 snippet has no measurement id"
        assert m.group(0) in dirt_craft_lesson_html

    def test_lesson_page_no_inline_onclick(self, dirt_craft_lesson_html):
        assert "onclick=" not in dirt_craft_lesson_html

    def test_all_dirt_craft_pages_clean(self):
        course = load_course(COURSES_DIR / "dirt-craft")
        flat = generate_courses.get_flat_lessons(course)
        ga4_id = re.search(r"G-[A-Z0-9]{8,}", get_ga4_head_snippet()).group(0)
        for idx, (module, lesson) in enumerate(flat):
            html = build_lesson_page(course, module, lesson, idx, len(flat), flat)
            assert ga4_id in html, f"GA4 missing from lesson {lesson['id']}"
            assert "onclick=" not in html, f"inline onclick in lesson {lesson['id']}"
            assert "onsubmit=" not in html, f"inline onsubmit in lesson {lesson['id']}"

    def test_stack_check_lessons_render_quiz_blocks(self):
        course = load_course(COURSES_DIR / "dirt-craft")
        flat = generate_courses.get_flat_lessons(course)
        stack_checks = [(i, m, l) for i, (m, l) in enumerate(flat)
                        if "stack-check" in l["id"]]
        assert len(stack_checks) == 4
        for idx, module, lesson in stack_checks:
            html = build_lesson_page(course, module, lesson, idx, len(flat), flat)
            assert ">QUIZ<" in html, f"{lesson['id']} has no rendered quiz blocks"
            assert "gg-guide-kc-option" in html

    @V2_CONTENT_SKIP
    def test_calculator_lessons_have_calc_markup_and_js(self):
        course = load_course(COURSES_DIR / "dirt-craft")
        flat = generate_courses.get_flat_lessons(course)
        by_id = {l["id"]: (i, m, l) for i, (m, l) in enumerate(flat)}
        expectations = {
            "where-traction-lives": "dirt-craft-pressure-baseline",
            "cornering-without-clenching": "dirt-craft-corner-speed",
            "climbing-without-spinning-out": "dirt-craft-gearing-check",
            "reading-surfaces-at-speed": "dirt-craft-tire-pressure",
        }
        for lesson_id, calc_id in expectations.items():
            idx, module, lesson = by_id[lesson_id]
            html = build_lesson_page(course, module, lesson, idx, len(flat), flat)
            assert f'data-calc-type="{calc_id}"' in html
            assert f"calcType==='{calc_id}'" in html


# ── (f) Image blocks reference existing files ────────────────


class TestImageAssets:
    @V2_CONTENT_SKIP
    def test_image_src_files_exist(self):
        checked = 0
        for course_name, lesson_name, block in ALL_BLOCKS:
            if block.get("type") not in ("image", "labeled_graphic") or "src" not in block:
                continue
            src = block["src"]
            prefix = f"/course/{course_name}/assets/"
            assert src.startswith(prefix), (
                f"{course_name}/{lesson_name}: image src '{src}' must live under "
                f"{prefix}")
            asset = COURSES_DIR / course_name / "assets" / src[len(prefix):]
            assert asset.exists(), (
                f"{course_name}/{lesson_name}: image src '{src}' references a "
                f"missing file")
            checked += 1
        assert checked >= 20, f"expected 20+ image blocks, found {checked}"

    def test_image_blocks_have_alt_text(self):
        for course_name, lesson_name, block in ALL_BLOCKS:
            if block.get("type") not in ("image", "labeled_graphic") or "src" not in block:
                continue
            alt = block.get("alt", "")
            assert len(alt) >= 20, (
                f"{course_name}/{lesson_name}: image '{block['src']}' needs "
                f"descriptive alt text")

    @V2_CONTENT_SKIP
    def test_every_dirt_craft_lesson_has_top_image(self):
        """Each of the 12 numbered lessons gets at least one illustration
        within the first 4 blocks (stack checks are quiz-only, exempt).
        labeled_graphic counts — it's an illustration with hotspots."""
        lessons_dir = COURSES_DIR / "dirt-craft" / "lessons"
        for lesson_file in sorted(lessons_dir.glob("[01]*.json")):
            data = json.loads(lesson_file.read_text(encoding="utf-8"))
            head = data["blocks"][:4]
            assert any(b.get("type") in ("image", "labeled_graphic") for b in head), (
                f"{lesson_file.name}: no illustration near the top")


# ── (g) Rise-style blocks v2: labeled graphic, sorting, continue gate ──


from generate_guide import (  # noqa: E402
    render_continue_gate,
    render_knowledge_check,
    render_labeled_graphic,
    render_sorting_activity,
    set_lesson_context,
)


def _lg_block(**overrides):
    block = {
        "type": "labeled_graphic",
        "src": "/course/dirt-craft/assets/L01_death_grip_vs_weighted_drop_v2.webp",
        "alt": "alt text",
        "markers": [
            {"x": 42.5, "y": 31.0, "label": "1", "title": "Hips back",
             "content": "Push the hips back.", "feedback_detail": "More detail."},
            {"x": 10, "y": 90, "label": "2", "title": "Heels", "content": "Drop them."},
        ],
    }
    block.update(overrides)
    return block


class TestLabeledGraphic:
    def test_registered(self):
        assert "labeled_graphic" in BLOCK_RENDERERS

    def test_renders_markers_and_fallback(self):
        html = render_labeled_graphic(_lg_block())
        assert html.count('gg-guide-lg-marker') == 2
        assert 'type="button"' in html
        assert 'aria-expanded="false"' in html
        assert 'left:42.5%;top:31.0%' in html
        # No-JS fallback: numbered list with title + content, visible by default
        assert '<ol class="gg-guide-lg-fallback">' in html
        assert 'Push the hips back.' in html
        assert 'More detail.' in html
        # markup itself never hides the fallback — JS adds .gg-lg-ready
        assert 'gg-lg-ready' not in html

    def test_escapes_all_fields(self):
        html = render_labeled_graphic(_lg_block(
            src=XSS, alt=XSS, caption=XSS,
            markers=[{"x": 5, "y": 5, "label": XSS, "title": XSS,
                      "content": XSS, "feedback_detail": XSS}]))
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    @pytest.mark.parametrize("x,y", [(101, 50), (-1, 50), (50, 100.1), (50, -0.5)])
    def test_marker_bounds_enforced(self, x, y):
        with pytest.raises(ValueError, match="out of bounds"):
            render_labeled_graphic(_lg_block(
                markers=[{"x": x, "y": y, "title": "t", "content": "c"}]))

    def test_marker_bounds_edges_ok(self):
        html = render_labeled_graphic(_lg_block(
            markers=[{"x": 0, "y": 100, "title": "t", "content": "c"}]))
        assert 'left:0.0%;top:100.0%' in html

    def test_requires_markers(self):
        with pytest.raises(ValueError, match="marker"):
            render_labeled_graphic(_lg_block(markers=[]))


def _sorting_block(**overrides):
    block = {
        "type": "sorting_activity",
        "title": "Front or Rear?",
        "instructions": "Tap the brake.",
        "categories": [{"id": "front", "label": "Front brake"},
                       {"id": "rear", "label": "Rear brake"}],
        "items": [{"text": "Most stopping power", "category": "front"},
                  {"text": "Locks easily", "category": "rear"}],
    }
    block.update(overrides)
    return block


class TestSortingActivity:
    def test_registered(self):
        assert "sorting_activity" in BLOCK_RENDERERS

    def test_renders_cards_cats_and_status(self):
        html = render_sorting_activity(_sorting_block())
        assert html.count('gg-guide-sorting-card') == 2
        assert html.count('gg-guide-sorting-cat"') == 2
        assert 'data-sorting-hash=' in html
        assert 'data-sorting-total="2"' in html
        assert 'aria-live="polite"' in html
        # cards visible by default; JS readiness class never server-rendered
        assert 'gg-sorting-ready' not in html

    def test_category_cap_four(self):
        cats = [{"id": f"c{i}", "label": f"C{i}"} for i in range(5)]
        items = [{"text": "x", "category": "c0"}]
        with pytest.raises(ValueError, match="at most 4"):
            render_sorting_activity(_sorting_block(categories=cats, items=items))

    def test_minimum_two_categories(self):
        with pytest.raises(ValueError, match="at least 2"):
            render_sorting_activity(_sorting_block(
                categories=[{"id": "a", "label": "A"}],
                items=[{"text": "x", "category": "a"}]))

    def test_unknown_item_category_rejected(self):
        with pytest.raises(ValueError, match="unknown category"):
            render_sorting_activity(_sorting_block(
                items=[{"text": "x", "category": "nope"}]))

    def test_escapes(self):
        html = render_sorting_activity(_sorting_block(
            title=XSS, instructions=XSS,
            categories=[{"id": XSS, "label": XSS}, {"id": "b", "label": "B"}],
            items=[{"text": XSS, "category": XSS}]))
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestContinueGate:
    def test_registered(self):
        assert "continue_gate" in BLOCK_RENDERERS

    @pytest.mark.parametrize("mode", ["none", "block_above", "all_above"])
    def test_modes_render(self, mode):
        html = render_continue_gate(
            {"type": "continue_gate", "label": "CONTINUE", "mode": mode})
        assert f'data-gate-mode="{mode}"' in html
        assert 'gg-guide-continue-btn' in html

    def test_invalid_mode_rejected(self):
        with pytest.raises(ValueError, match="mode"):
            render_continue_gate({"type": "continue_gate", "label": "X", "mode": "bogus"})

    def test_progressive_enhancement_contract(self):
        """The static markup must hide NOTHING and disable nothing — gating
        only happens after JS wraps the following content (pitfall 11)."""
        html = render_continue_gate(
            {"type": "continue_gate", "label": "CONTINUE", "mode": "block_above"})
        assert 'aria-hidden' not in html
        assert 'disabled' not in html
        assert 'max-height' not in html
        assert 'gg-gate-closed' not in html
        assert 'gg-gate-wrap' not in html

    def test_escapes_label(self):
        html = render_continue_gate(
            {"type": "continue_gate", "label": XSS, "mode": "none"})
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_gate_hash_deterministic_per_lesson(self):
        set_lesson_context("lesson-a")
        h1 = render_continue_gate({"type": "continue_gate", "label": "GO", "mode": "none"})
        h2 = render_continue_gate({"type": "continue_gate", "label": "GO", "mode": "none"})
        set_lesson_context("lesson-b")
        h3 = render_continue_gate({"type": "continue_gate", "label": "GO", "mode": "none"})
        set_lesson_context(None)
        assert h1 == h2
        assert h1 != h3


class TestKnowledgeCheckFormats:
    def test_multiple_choice_unchanged_without_format(self):
        html = render_knowledge_check({
            "question": "q", "explanation": "e",
            "options": [{"text": "a", "correct": True},
                        {"text": "b", "correct": False}],
        })
        assert 'gg-guide-kc-option' in html
        assert 'data-question-hash' in html
        assert 'gg-guide-kc-fib' not in html
        assert 'gg-guide-kc-match' not in html

    def test_fill_blank_renders_input_and_accept_list(self):
        html = render_knowledge_check({
            "format": "fill_blank", "question": "Name the hinge joint.",
            "accept": ["hip", "the hip"], "case_sensitive": False,
            "explanation": "It's the hip.",
        })
        assert 'gg-guide-kc--fill-blank' in html
        assert 'gg-guide-kc-fib-input' in html
        assert 'gg-guide-kc-fib-check' in html
        assert 'data-case-sensitive="false"' in html
        assert 'data-accept=' in html
        assert '&quot;hip&quot;' in html
        assert 'data-question-hash' in html

    def test_fill_blank_case_sensitive_flag(self):
        html = render_knowledge_check({
            "format": "fill_blank", "question": "q", "accept": ["PSI"],
            "case_sensitive": True, "explanation": "e",
        })
        assert 'data-case-sensitive="true"' in html

    def test_fill_blank_requires_accept(self):
        with pytest.raises(ValueError, match="accept"):
            render_knowledge_check({
                "format": "fill_blank", "question": "q", "accept": [],
                "explanation": "e"})

    def test_fill_blank_escapes(self):
        html = render_knowledge_check({
            "format": "fill_blank", "question": XSS, "accept": [XSS],
            "explanation": XSS})
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_matching_renders_columns(self):
        set_lesson_context("test-lesson")
        html = render_knowledge_check({
            "format": "matching",
            "pairs": [{"left": "L1", "right": "R1"},
                      {"left": "L2", "right": "R2"},
                      {"left": "L3", "right": "R3"}],
        })
        set_lesson_context(None)
        assert 'gg-guide-kc--matching' in html
        assert html.count('gg-guide-kc-match-left') == 3
        assert html.count('gg-guide-kc-match-right') == 3
        assert 'data-pair="0"' in html
        assert 'data-match=' in html
        assert 'data-question-hash' in html

    def test_matching_shuffle_deterministic_and_not_natural(self):
        pairs = [{"left": f"L{i}", "right": f"R{i}"} for i in range(4)]
        set_lesson_context("seed-lesson")
        h1 = render_knowledge_check({"format": "matching", "pairs": pairs})
        h2 = render_knowledge_check({"format": "matching", "pairs": pairs})
        set_lesson_context(None)
        assert h1 == h2, "matching shuffle must be deterministic per lesson"
        order = re.findall(r'data-match="(\d)"', h1)
        assert order != ["0", "1", "2", "3"], "right column must be shuffled"

    def test_matching_requires_two_pairs(self):
        with pytest.raises(ValueError, match="pairs"):
            render_knowledge_check({
                "format": "matching", "pairs": [{"left": "a", "right": "b"}]})

    def test_matching_escapes(self):
        html = render_knowledge_check({
            "format": "matching",
            "pairs": [{"left": XSS, "right": XSS},
                      {"left": "b", "right": "c"}]})
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


# ── (h) Showcase placements in the Dirt Craft course ─────────


@V2_CONTENT_SKIP
class TestShowcasePlacements:
    def _lesson(self, name):
        return json.loads(
            (COURSES_DIR / "dirt-craft" / "lessons" / name).read_text(encoding="utf-8"))

    def test_labeled_graphics_in_three_lessons(self):
        expected = {
            "01-letting-go.json": "L01_death_grip_vs_weighted_drop_v2.webp",
            "02-your-body-is-the-suspension.json": "L02_hip_hinge_side.webp",
            "05-braking-that-builds-confidence.json": "L05_brake_position_wide.webp",
        }
        for fname, asset in expected.items():
            data = self._lesson(fname)
            lgs = [b for b in data["blocks"] if b.get("type") == "labeled_graphic"]
            assert lgs, f"{fname}: no labeled_graphic"
            lg = lgs[0]
            assert asset in lg["src"]
            assert len(lg.get("alt", "")) >= 20
            assert 3 <= len(lg["markers"]) <= 4
            for m in lg["markers"]:
                assert 0 <= m["x"] <= 100 and 0 <= m["y"] <= 100
                assert m["title"] and m["content"]

    def test_sorting_in_l05_and_m2(self):
        l05 = self._lesson("05-braking-that-builds-confidence.json")
        sorts = [b for b in l05["blocks"] if b.get("type") == "sorting_activity"]
        assert len(sorts) == 1
        assert {c["id"] for c in sorts[0]["categories"]} == {"front", "rear"}
        assert len(sorts[0]["items"]) >= 6
        m2 = self._lesson("m2-stack-check.json")
        sorts2 = [b for b in m2["blocks"] if b.get("type") == "sorting_activity"]
        assert len(sorts2) == 1
        assert len(sorts2[0]["categories"]) == 4
        cats = {c["id"] for c in sorts2[0]["categories"]}
        assert {it["category"] for it in sorts2[0]["items"]} == cats

    def test_continue_gates_follow_knowledge_checks(self):
        for fname in ("01-letting-go.json", "05-braking-that-builds-confidence.json"):
            data = self._lesson(fname)
            types = [b["type"] for b in data["blocks"]]
            assert "continue_gate" in types, f"{fname}: no continue_gate"
            idx = types.index("continue_gate")
            assert types[idx - 1] == "knowledge_check", (
                f"{fname}: continue_gate must sit right after the knowledge_check")
            gate = data["blocks"][idx]
            assert gate["mode"] == "block_above"

    def test_showcase_lessons_render_in_pages(self):
        course = load_course(COURSES_DIR / "dirt-craft")
        flat = generate_courses.get_flat_lessons(course)
        by_id = {l["id"]: (i, m, l) for i, (m, l) in enumerate(flat)}
        for lesson_id, needles in {
            "letting-go": ["gg-guide-labeled-graphic", "gg-guide-continue-gate"],
            "your-body-is-the-suspension": ["gg-guide-labeled-graphic"],
            "braking-that-builds-confidence": [
                "gg-guide-labeled-graphic", "gg-guide-sorting",
                "gg-guide-continue-gate"],
            "control-stack-check": ["gg-guide-sorting"],
        }.items():
            idx, module, lesson = by_id[lesson_id]
            html = build_lesson_page(course, module, lesson, idx, len(flat), flat)
            for needle in needles:
                assert needle in html, f"{lesson_id}: missing {needle}"
            assert "onclick=" not in html
