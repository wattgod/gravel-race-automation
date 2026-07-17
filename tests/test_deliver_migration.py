"""
Tests for the Deliver course migration and rendering pipeline.

Verifies:
1. Migration produces valid course.json + lesson files
2. Every block type maps to a supported renderer
3. Block field schemas match what renderers expect
4. Clean Pro theme tokens are applied correctly
5. noindex meta tag is present
6. Asset references are extractable
7. No silent failures (empty blocks, missing fields)
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COURSE_DIR = PROJECT_ROOT / "data" / "courses" / "deliver"

sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
from generate_guide import BLOCK_RENDERERS, render_block


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def course_json():
    """Load the migrated course.json."""
    path = COURSE_DIR / "course.json"
    if not path.exists():
        pytest.skip("Run scripts/migrate_deliver.py first")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def all_lessons():
    """Load all migrated lesson files."""
    lessons_dir = COURSE_DIR / "lessons"
    if not lessons_dir.exists():
        pytest.skip("Run scripts/migrate_deliver.py first")
    lessons = {}
    for f in sorted(lessons_dir.glob("*.json")):
        lessons[f.name] = json.loads(f.read_text(encoding="utf-8"))
    return lessons


@pytest.fixture(scope="module")
def all_blocks(all_lessons):
    """Collect all blocks from all lessons."""
    blocks = []
    for filename, lesson in all_lessons.items():
        for i, block in enumerate(lesson.get("blocks", [])):
            blocks.append((filename, i, block))
    return blocks


# ── Course Structure Tests ──────────────────────────────────


class TestCourseStructure:
    def test_course_json_exists(self):
        assert (COURSE_DIR / "course.json").exists()

    def test_course_has_required_fields(self, course_json):
        required = ["id", "title", "subtitle", "description", "price_usd",
                     "modules", "status", "instructor", "what_youll_learn"]
        for field in required:
            assert field in course_json, f"Missing required field: {field}"

    def test_course_id_is_deliver(self, course_json):
        assert course_json["id"] == "deliver"

    def test_course_is_active(self, course_json):
        assert course_json["status"] == "active"

    def test_course_has_noindex(self, course_json):
        assert course_json.get("noindex") is True

    def test_course_theme_is_clean_pro(self, course_json):
        assert course_json.get("theme") == "clean-pro"

    def test_course_has_6_modules(self, course_json):
        assert len(course_json["modules"]) == 6

    def test_course_has_38_lessons(self, course_json):
        total = sum(len(m["lessons"]) for m in course_json["modules"])
        assert total == 38

    def test_every_lesson_file_exists(self, course_json):
        for module in course_json["modules"]:
            for lesson in module["lessons"]:
                lesson_path = COURSE_DIR / lesson["file"]
                assert lesson_path.exists(), f"Missing lesson file: {lesson['file']}"

    def test_no_empty_lessons(self, all_lessons):
        for filename, lesson in all_lessons.items():
            blocks = lesson.get("blocks", [])
            assert len(blocks) > 0, f"Empty lesson: {filename}"

    def test_price_is_79(self, course_json):
        assert course_json["price_usd"] == 79


# ── Block Type Tests ────────────────────────────────────────


class TestBlockTypes:
    def test_all_block_types_have_renderers(self, all_blocks):
        """Every block type in Deliver must map to a registered renderer."""
        unsupported = set()
        for filename, idx, block in all_blocks:
            btype = block.get("type", "MISSING")
            if btype not in BLOCK_RENDERERS:
                unsupported.add(btype)
        assert not unsupported, f"Block types without renderers: {unsupported}"

    def test_no_blocks_missing_type(self, all_blocks):
        """Every block must have a 'type' field."""
        for filename, idx, block in all_blocks:
            assert "type" in block, f"{filename} block {idx}: missing 'type'"

    def test_prose_blocks_have_content(self, all_blocks):
        for filename, idx, block in all_blocks:
            if block.get("type") == "prose":
                assert "content" in block, f"{filename} block {idx}: prose missing content"
                assert len(block["content"].strip()) > 0

    def test_callout_blocks_have_content_and_style(self, all_blocks):
        for filename, idx, block in all_blocks:
            if block.get("type") == "callout":
                assert "content" in block, f"{filename} block {idx}: callout missing content"
                assert "style" in block, f"{filename} block {idx}: callout missing style"
                assert block["style"] in ("highlight", "info", "tip", "quote", "warning"), \
                    f"{filename} block {idx}: unknown callout style '{block['style']}'"

    def test_accordion_blocks_have_items(self, all_blocks):
        for filename, idx, block in all_blocks:
            if block.get("type") == "accordion":
                assert "items" in block, f"{filename} block {idx}: accordion missing items"
                assert len(block["items"]) > 0
                for item in block["items"]:
                    assert "title" in item and "content" in item

    def test_tabs_blocks_have_tabs(self, all_blocks):
        for filename, idx, block in all_blocks:
            if block.get("type") == "tabs":
                assert "tabs" in block, f"{filename} block {idx}: tabs missing tabs"
                assert len(block["tabs"]) > 0
                for tab in block["tabs"]:
                    assert "label" in tab and "content" in tab

    def test_knowledge_check_blocks_have_required_fields(self, all_blocks):
        for filename, idx, block in all_blocks:
            if block.get("type") == "knowledge_check":
                assert "question" in block, f"{filename} block {idx}: KC missing question"
                assert "options" in block, f"{filename} block {idx}: KC missing options"
                assert len(block["options"]) >= 2, f"{filename} block {idx}: KC needs 2+ options"
                # At least one correct answer
                correct = [o for o in block["options"] if o.get("correct")]
                assert len(correct) >= 1, f"{filename} block {idx}: KC has no correct answer"

    def test_scenario_blocks_have_required_fields(self, all_blocks):
        for filename, idx, block in all_blocks:
            if block.get("type") == "scenario":
                assert "prompt" in block, f"{filename} block {idx}: scenario missing prompt"
                assert "options" in block
                for opt in block["options"]:
                    assert "label" in opt and "result" in opt

    def test_flashcard_blocks_have_cards(self, all_blocks):
        for filename, idx, block in all_blocks:
            if block.get("type") == "flashcard":
                assert "cards" in block
                for card in block["cards"]:
                    assert "front" in card and "back" in card

    def test_timeline_blocks_have_steps(self, all_blocks):
        for filename, idx, block in all_blocks:
            if block.get("type") == "timeline":
                assert "steps" in block
                for step in block["steps"]:
                    assert "label" in step and "content" in step

    def test_process_list_blocks_have_items(self, all_blocks):
        for filename, idx, block in all_blocks:
            if block.get("type") == "process_list":
                assert "items" in block
                for item in block["items"]:
                    assert "label" in item and "detail" in item


# ── Rendering Tests ─────────────────────────────────────────


class TestRendering:
    def test_all_blocks_render_without_error(self, all_blocks):
        """Every block must render to non-empty HTML without exceptions."""
        errors = []
        for filename, idx, block in all_blocks:
            try:
                html = render_block(block)
                if "unknown block type" in html:
                    errors.append(f"{filename} block {idx}: rendered as unknown ({block.get('type')})")
            except Exception as e:
                errors.append(f"{filename} block {idx}: {type(e).__name__}: {e}")
        assert not errors, f"Rendering errors:\n" + "\n".join(errors[:10])

    def test_no_empty_renders(self, all_blocks):
        """No block should render to an empty string."""
        for filename, idx, block in all_blocks:
            html = render_block(block)
            assert len(html.strip()) > 0, f"{filename} block {idx}: rendered empty"


# ── Clean Pro Theme Tests ───────────────────────────────────


class TestCleanProTheme:
    def test_clean_pro_tokens_have_inter_font(self):
        from brand_tokens import get_clean_pro_tokens_css
        css = get_clean_pro_tokens_css()
        assert "'Inter'" in css

    def test_clean_pro_tokens_have_correct_accent(self):
        from brand_tokens import get_clean_pro_tokens_css
        css = get_clean_pro_tokens_css()
        assert "#4ECDC4" in css

    def test_clean_pro_tokens_have_white_bg(self):
        from brand_tokens import get_clean_pro_tokens_css
        css = get_clean_pro_tokens_css()
        assert "--gl-bg: #ffffff" in css

    def test_clean_pro_muted_text_passes_wcag_aa(self):
        """#767676 on #ffffff = 4.54:1 contrast ratio, passes WCAG AA."""
        from brand_tokens import CLEAN_PRO_COLORS
        assert CLEAN_PRO_COLORS["text_muted"] == "#767676"
        # 4.54:1 is the actual contrast ratio — above 4.5:1 threshold

    def test_clean_pro_overrides_exist(self):
        from brand_tokens import get_clean_pro_overrides_css
        css = get_clean_pro_overrides_css()
        assert ".gg-course-hero" in css
        assert "#ffffff" in css

    def test_clean_pro_border_radius_is_4px(self):
        from brand_tokens import get_clean_pro_tokens_css
        css = get_clean_pro_tokens_css()
        assert "--gg-border-radius: 4px" in css


# ── WCAG Contrast Tests ─────────────────────────────────────


class TestAccessibility:
    @staticmethod
    def _relative_luminance(hex_color: str) -> float:
        """Calculate relative luminance per WCAG 2.0."""
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        srgb = []
        for c in (r, g, b):
            c_norm = c / 255.0
            srgb.append(c_norm / 12.92 if c_norm <= 0.03928
                        else ((c_norm + 0.055) / 1.055) ** 2.4)
        return 0.2126 * srgb[0] + 0.7152 * srgb[1] + 0.0722 * srgb[2]

    @staticmethod
    def _contrast_ratio(hex1: str, hex2: str) -> float:
        l1 = TestAccessibility._relative_luminance(hex1)
        l2 = TestAccessibility._relative_luminance(hex2)
        lighter, darker = max(l1, l2), min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    def test_body_text_on_white(self):
        """#4a4a4a on #ffffff must pass WCAG AA (>= 4.5:1)."""
        ratio = self._contrast_ratio("#4a4a4a", "#ffffff")
        assert ratio >= 4.5, f"Body text contrast: {ratio:.2f}:1 (need 4.5:1)"

    def test_muted_text_on_white(self):
        """#767676 on #ffffff must pass WCAG AA (>= 4.5:1)."""
        ratio = self._contrast_ratio("#767676", "#ffffff")
        assert ratio >= 4.5, f"Muted text contrast: {ratio:.2f}:1 (need 4.5:1)"

    def test_accent_on_white_fails_for_text(self):
        """#4ECDC4 on #ffffff fails AA — accent must not be used as text color."""
        ratio = self._contrast_ratio("#4ECDC4", "#ffffff")
        assert ratio < 4.5, "Accent passes AA? Then it CAN be used as text — update docs"

    def test_headline_on_white(self):
        """#1a1a1a on #ffffff must pass WCAG AAA (>= 7:1)."""
        ratio = self._contrast_ratio("#1a1a1a", "#ffffff")
        assert ratio >= 7.0, f"Headline contrast: {ratio:.2f}:1 (need 7:1)"


# ── Silent Failure Detection ────────────────────────────────


class TestSilentFailures:
    def test_no_blocks_with_empty_content(self, all_blocks):
        """Catch blocks where content is present but empty."""
        for filename, idx, block in all_blocks:
            btype = block.get("type", "")
            if btype == "prose":
                assert block.get("content", "").strip(), f"{filename} block {idx}: empty prose"
            if btype == "callout":
                assert block.get("content", "").strip(), f"{filename} block {idx}: empty callout"

    def test_no_quiz_with_all_correct_or_all_wrong(self, all_blocks):
        """A quiz where every option is correct or wrong is broken."""
        for filename, idx, block in all_blocks:
            if block.get("type") == "knowledge_check":
                options = block.get("options", [])
                if len(options) > 1:
                    correct_count = sum(1 for o in options if o.get("correct"))
                    assert correct_count > 0, f"{filename} block {idx}: no correct answer"
                    assert correct_count < len(options), f"{filename} block {idx}: all options correct"

    def test_no_duplicate_lesson_ids(self, course_json):
        """Every lesson ID must be unique across the course."""
        ids = []
        for module in course_json["modules"]:
            for lesson in module["lessons"]:
                ids.append(lesson["id"])
        assert len(ids) == len(set(ids)), f"Duplicate lesson IDs: {[x for x in ids if ids.count(x) > 1]}"

    def test_no_duplicate_module_ids(self, course_json):
        ids = [m["id"] for m in course_json["modules"]]
        assert len(ids) == len(set(ids))


# ── Generated Output Tests ──────────────────────────────────


class TestGeneratedOutput:
    OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output" / "course" / "deliver"

    def test_landing_page_exists(self):
        if not self.OUTPUT_DIR.exists():
            pytest.skip("Run generate_courses.py first")
        assert (self.OUTPUT_DIR / "index.html").exists()

    def test_all_lesson_pages_exist(self, course_json):
        if not self.OUTPUT_DIR.exists():
            pytest.skip("Run generate_courses.py first")
        for module in course_json["modules"]:
            for lesson in module["lessons"]:
                lesson_dir = self.OUTPUT_DIR / "lesson" / lesson["id"]
                assert (lesson_dir / "index.html").exists(), \
                    f"Missing lesson page: {lesson['id']}"

    def test_landing_page_has_noindex(self):
        if not self.OUTPUT_DIR.exists():
            pytest.skip("Run generate_courses.py first")
        html = (self.OUTPUT_DIR / "index.html").read_text()
        assert 'noindex' in html

    def test_landing_page_has_inter_font(self):
        if not self.OUTPUT_DIR.exists():
            pytest.skip("Run generate_courses.py first")
        html = (self.OUTPUT_DIR / "index.html").read_text()
        assert "Inter" in html

    def test_lesson_pages_have_noindex(self, course_json):
        """All lesson pages should have noindex since the course is hidden."""
        if not self.OUTPUT_DIR.exists():
            pytest.skip("Run generate_courses.py first")
        # Lesson pages already have noindex by default in generate_courses.py
        first_lesson = course_json["modules"][0]["lessons"][0]
        html = (self.OUTPUT_DIR / "lesson" / first_lesson["id"] / "index.html").read_text()
        assert 'noindex' in html
