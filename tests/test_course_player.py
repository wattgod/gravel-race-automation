"""Tests for the Rise-360-style course lesson player (Jun 2026 rebuild).

Guards:
  - two-column player layout: sidebar present, grouped by module, drawer
    toggle + scrim + floating chip for mobile
  - prev/next lesson navigation with titles, at top AND bottom
  - per-lesson duration estimates (sidebar, header, landing curriculum)
  - og:image / og:title / twitter:card meta on landing + lesson pages
  - entrance animations are progressive enhancement (content visible by
    default — pitfall 11) and reduced-motion guarded
  - prose blocks are never animation targets
  - lightbox + drawer GA4 events fire only on user interaction
  - the purchase gate contract is untouched (#gg-course-gate,
    #gg-course-verify-form, unlock flow)
  - no inline event handlers
"""
import math
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
from generate_courses import (
    _COURSE_PLAYER_JS,
    build_course_css,
    build_course_js,
    build_landing_page,
    build_lesson_page,
    estimate_lesson_minutes,
    format_course_total_time,
    lesson_drill_minutes,
    load_course,
)

PROJECT_ROOT = Path(__file__).parent.parent
COURSES_DIR = PROJECT_ROOT / "data" / "courses"


@pytest.fixture(scope="module")
def dirt_craft():
    return load_course(COURSES_DIR / "dirt-craft")


@pytest.fixture(scope="module")
def hydration():
    return load_course(COURSES_DIR / "gravel-hydration-mastery")


@pytest.fixture(scope="module")
def lesson_html(dirt_craft):
    flat = generate_courses.get_flat_lessons(dirt_craft)
    module, lesson = flat[0]
    return build_lesson_page(dirt_craft, module, lesson, 0, len(flat), flat)


@pytest.fixture(scope="module")
def mid_lesson_html(dirt_craft):
    """A lesson with both prev and next neighbours."""
    flat = generate_courses.get_flat_lessons(dirt_craft)
    module, lesson = flat[2]
    return build_lesson_page(dirt_craft, module, lesson, 2, len(flat), flat)


@pytest.fixture(scope="module")
def landing_html(dirt_craft, hydration):
    return build_landing_page(dirt_craft, all_courses=[dirt_craft, hydration])


@pytest.fixture(scope="module")
def course_css():
    return build_course_css()


@pytest.fixture(scope="module")
def course_js(dirt_craft):
    return build_course_js(dirt_craft, {})


# ── Two-column player layout ─────────────────────────────────


class TestSidebar:
    def test_sidebar_present_on_lesson_pages(self, lesson_html):
        assert 'id="gg-course-sidebar"' in lesson_html
        assert 'class="gg-course-layout"' in lesson_html
        assert '<main class="gg-course-main">' in lesson_html

    def test_sidebar_groups_lessons_by_module(self, lesson_html, dirt_craft):
        for module in dirt_craft["modules"]:
            assert f'<div class="gg-course-sidebar-module">{module["title"]}' \
                in lesson_html or module["title"] in lesson_html
        # one outline list per module
        assert lesson_html.count('gg-course-sidebar-module') >= len(dirt_craft["modules"])

    def test_sidebar_has_course_title_link_ring_and_xp(self, lesson_html):
        assert 'gg-course-sidebar-title' in lesson_html
        assert 'id="gg-ring-circle"' in lesson_html
        assert 'gg-xp-section' in lesson_html

    def test_current_lesson_highlighted(self, lesson_html):
        assert 'class="gg-current"' in lesson_html
        assert 'aria-current="page"' in lesson_html

    def test_every_lesson_listed_with_checkmark_slot(self, lesson_html, dirt_craft):
        total = dirt_craft["total_lessons"]
        assert lesson_html.count('data-lesson-id=') >= total

    def test_mobile_outline_bar_and_chip(self, lesson_html):
        assert 'id="gg-course-outline-toggle"' in lesson_html
        assert 'aria-controls="gg-course-sidebar"' in lesson_html
        assert 'aria-expanded="false"' in lesson_html
        assert 'id="gg-course-chip"' in lesson_html
        assert 'id="gg-course-scrim"' in lesson_html

    def test_desktop_sidebar_sticky_and_mobile_drawer_css(self, course_css):
        assert 'position:sticky' in course_css
        assert '.gg-course-sidebar-open' in course_css
        # drawer transition must be reduced-motion guarded
        m = re.search(
            r'@media\(max-width:1023px\) and \(prefers-reduced-motion:no-preference\)'
            r'\{\{?[^}]*\.gg-course-sidebar\{\{?transition', course_css)
        assert m, "drawer transition must be inside prefers-reduced-motion:no-preference"

    def test_main_column_prose_measure(self, course_css):
        assert 'max-width:760px' in course_css


# ── Lesson navigation ────────────────────────────────────────


class TestLessonNav:
    def test_nav_at_top_and_bottom(self, mid_lesson_html):
        assert 'gg-course-nav--top' in mid_lesson_html
        assert 'gg-course-nav--bottom' in mid_lesson_html

    def test_nav_buttons_carry_lesson_titles(self, mid_lesson_html, dirt_craft):
        flat = generate_courses.get_flat_lessons(dirt_craft)
        prev_title = flat[1][1]["title"]
        next_title = flat[3][1]["title"]
        assert 'gg-course-nav-title' in mid_lesson_html
        assert prev_title in mid_lesson_html
        assert next_title in mid_lesson_html

    def test_lesson_x_of_y_kept(self, mid_lesson_html):
        assert re.search(r'LESSON 03 OF \d{2}', mid_lesson_html)

    def test_complete_btn_has_next_url_for_auto_advance(self, mid_lesson_html):
        m = re.search(r'id="gg-course-complete-btn"[^>]*data-next-url="([^"]+)"',
                      mid_lesson_html, re.S)
        assert m and '/lesson/' in m.group(1)

    def test_auto_advance_in_js(self, course_js):
        assert "getAttribute('data-next-url')" in course_js
        assert 'window.location.href=nextUrl' in course_js


# ── Duration estimates ───────────────────────────────────────


class TestDurations:
    def test_methodology(self):
        lesson = {"blocks": [
            {"type": "prose", "content": " ".join(["word"] * 400)},
            {"type": "knowledge_check", "question": "q", "explanation": "e",
             "options": [{"text": "a", "correct": True}]},
            {"type": "image", "src": "/course/x/assets/a.webp", "alt": "alt"},
        ]}
        # 400+ words of text → ceil(words/200) + 1 interactive
        words = sum(generate_courses._count_words(b) for b in lesson["blocks"])
        assert estimate_lesson_minutes(lesson) == math.ceil(words / 200) + 1

    def test_minimum_one_minute(self):
        assert estimate_lesson_minutes({"blocks": []}) == 1

    def test_drill_minutes_separate(self):
        lesson = {"blocks": [
            {"type": "drill", "title": "t", "time_minutes": 25, "variants": []},
            {"type": "drill", "title": "t2", "time_minutes": 15, "variants": []},
        ]}
        assert lesson_drill_minutes(lesson) == 40
        # drill field time must NOT inflate reading estimate beyond +1/block
        assert estimate_lesson_minutes(lesson) <= 4

    def test_nested_accordion_blocks_counted(self):
        inner = {"type": "quiz", "question": "q", "explanation": "e",
                 "options": [{"text": "a", "correct": True}]}
        lesson = {"blocks": [{"type": "accordion",
                              "items": [{"title": "t", "blocks": [inner]}]}]}
        assert estimate_lesson_minutes(lesson) >= 2  # 1 min floor + 1 interactive

    def test_duration_in_lesson_header(self, lesson_html):
        assert re.search(r'gg-course-lesson-mins">~\d+ MIN<', lesson_html)

    def test_duration_in_sidebar_outline(self, lesson_html):
        assert re.search(r'gg-lesson-mins">~\d+ MIN<', lesson_html)

    def test_duration_in_landing_curriculum(self, landing_html):
        assert re.search(r'gg-course-lesson-mins-landing">~\d+ MIN<', landing_html)

    def test_total_course_time_on_landing(self, landing_html):
        assert 'gg-course-outline-total' in landing_html
        assert re.search(r'~[\d.]+ (hours?|minutes) of lessons', landing_html)

    def test_field_drills_called_out(self, dirt_craft):
        # dirt-craft has drills, so total time mentions field drills
        assert 'field drills' in format_course_total_time(dirt_craft)


class TestCoachInviteCourse:
    def test_coaching_start_manifest_and_lessons(self):
        course = load_course(COURSES_DIR / "coaching-start")
        assert course["access_model"] == "coach_invite"
        assert course["listed"] is False
        assert course["total_lessons"] == 7
        assert all(lesson["blocks"] for module in course["modules"]
                   for lesson in module["lessons"])

    def test_invite_landing_has_no_broken_checkout(self):
        course = load_course(COURSES_DIR / "coaching-start")
        html = generate_courses.build_landing_page(course, [course])
        assert "INCLUDED WITH COACHING" in html
        assert "SIGN IN TO START" in html
        assert 'href=""' not in html
        assert "ENROLL FOR $0" not in html

        flat = generate_courses.get_flat_lessons(course)
        module, lesson = flat[0]
        lesson_html = generate_courses.build_lesson_page(
            course, module, lesson, 0, len(flat), flat)
        assert "COACHING ONBOARDING" in lesson_html
        assert 'id="gg-course-invite-signin"' in lesson_html
        assert "ENROLL FOR $0" not in lesson_html
        assert 'href=""' not in lesson_html

    def test_invite_course_is_not_listed_in_store_index(self):
        invite = load_course(COURSES_DIR / "coaching-start")
        public = load_course(COURSES_DIR / "dirt-craft")
        html = generate_courses.build_course_index([invite, public])
        assert "Dirt Craft" in html
        assert "Your Coaching Operating System" not in html


# ── OG / social meta ─────────────────────────────────────────


class TestOgMeta:
    def test_landing_has_og_image(self, landing_html):
        assert 'property="og:image"' in landing_html
        assert '/course/assets/course-dirt-craft-og.png' in landing_html
        assert 'name="twitter:card" content="summary_large_image"' in landing_html

    def test_lesson_has_og_image_and_title(self, lesson_html):
        assert 'property="og:image"' in lesson_html
        assert '/course/assets/course-dirt-craft-og.png' in lesson_html
        assert 'property="og:title"' in lesson_html
        assert 'property="og:description"' in lesson_html

    def test_og_image_files_exist(self):
        assets = PROJECT_ROOT / "wordpress" / "output" / "course" / "assets"
        if not assets.exists():
            pytest.skip(
                "course OG assets not built here (run "
                "scripts/generate_course_og.py; needs Pillow)")
        for course_dir in sorted(COURSES_DIR.iterdir()):
            course = load_course(course_dir)
            if not course or not course.get("og_image"):
                continue
            assert (assets / course["og_image"]).exists(), \
                f"og_image missing: {course['og_image']}"


# ── Entrance animations: progressive enhancement contract ────


class TestAnimations:
    def test_content_visible_by_default(self, course_css):
        """opacity:0 must only apply under body.gg-anim-ready, and only
        inside a prefers-reduced-motion:no-preference media query."""
        bare_hidden = re.findall(
            r'(?<!gg-anim-ready )\.gg-course-anim\s*\{\{?[^}]*opacity:0', course_css)
        assert not bare_hidden, "blocks must be visible without .gg-anim-ready"
        assert 'body.gg-anim-ready .gg-course-anim' in course_css
        # the hidden state lives inside the no-preference media query
        media_idx = course_css.find('@media(prefers-reduced-motion:no-preference)')
        hidden_idx = course_css.find('body.gg-anim-ready .gg-course-anim')
        assert -1 < media_idx < hidden_idx

    def test_js_adds_ready_class(self):
        assert "classList.add('gg-anim-ready')" in _COURSE_PLAYER_JS

    def test_js_respects_reduced_motion(self):
        assert "prefers-reduced-motion: reduce" in _COURSE_PLAYER_JS

    def test_js_guards_intersection_observer(self):
        assert "'IntersectionObserver' in window" in _COURSE_PLAYER_JS

    def test_animate_once_threshold(self):
        assert 'io.unobserve' in _COURSE_PLAYER_JS
        assert 'threshold:0.15' in _COURSE_PLAYER_JS

    def test_prose_never_an_animation_target(self):
        m = re.search(r'NON_TEXT_BLOCKS=\[(.*?)\]', _COURSE_PLAYER_JS, re.S)
        assert m, "animation target list missing"
        targets = m.group(1)
        assert 'prose' not in targets
        # no bare element selectors (p, h2, li...) — classes only
        for sel in re.findall(r"'([^']+)'", targets):
            assert sel.startswith('.gg-guide-'), f"unexpected target: {sel}"

    def test_motion_css_reduced_motion_guarded(self, course_css):
        """Every keyframe animation must live inside a no-preference media query."""
        for kf in re.findall(r'@keyframes ([\w-]+)', course_css):
            idx = course_css.find(f'@keyframes {kf}')
            preceding = course_css[:idx]
            last_media = preceding.rfind('prefers-reduced-motion:no-preference')
            assert last_media != -1, f"@keyframes {kf} not reduced-motion guarded"


# ── Block polish ─────────────────────────────────────────────


class TestBlockPolish:
    def test_kc_per_option_feedback_rendered(self):
        from generate_guide import render_knowledge_check
        html = render_knowledge_check({
            "question": "q", "explanation": "fallback",
            "options": [
                {"text": "a", "correct": True, "feedback": "Right — here's why."},
                {"text": "b", "correct": False},
            ],
        })
        assert 'data-feedback-index="0"' in html
        assert 'data-feedback-index="1"' not in html
        assert 'gg-guide-kc-explanation-default' in html

    def test_kc_feedback_escaped(self):
        from generate_guide import render_knowledge_check
        html = render_knowledge_check({
            "question": "q", "explanation": "e",
            "options": [{"text": "a", "correct": True,
                         "feedback": '<script>alert(1)</script>'}],
        })
        assert '<script>' not in html

    def test_kc_js_uses_feedback_and_flash_shake(self, course_js):
        assert 'gg-guide-kc-feedback[data-feedback-index=' in course_js
        assert 'gg-kc-flash' in course_js
        assert 'gg-kc-shake' in course_js

    def test_accordion_one_open_at_a_time(self, course_js):
        assert 'closeIfAccordion' in course_js
        assert 'setAccordion' in course_js

    def test_tabs_arrow_key_navigation(self, course_js):
        assert "e.key==='ArrowRight'" in course_js
        assert "e.key==='ArrowLeft'" in course_js
        assert 'gg-tab-fade' in course_js

    def test_lightbox_present_and_keyboard_accessible(self):
        assert 'gg-course-lightbox' in _COURSE_PLAYER_JS
        assert "e.key==='Escape'" in _COURSE_PLAYER_JS
        assert "setAttribute('tabindex','0')" in _COURSE_PLAYER_JS
        assert "aria-label" in _COURSE_PLAYER_JS

    def test_lightbox_targets_content_images_only(self):
        m = re.search(r"querySelectorAll\('([^']*gg-guide-img-el[^']*)'\)",
                      _COURSE_PLAYER_JS)
        assert m and '.gg-course-lesson-body' in m.group(1)

    def test_stepper_builds_rail_and_controls(self):
        assert 'gg-tool-rail' in _COURSE_PLAYER_JS
        assert 'gg-tool-ctrl' in _COURSE_PLAYER_JS
        assert 'touchstart' in _COURSE_PLAYER_JS  # swipeable on mobile

    def test_flashcard_hint_hidden_after_first_flip(self, course_js, course_css):
        assert 'gg-fc-touched' in course_js
        assert '.gg-fc-touched .gg-guide-flashcard::after' in course_css


# ── GA4 events: manual interactions only ─────────────────────


class TestGA4Events:
    def test_course_lesson_complete_event(self, course_js):
        assert "'course_lesson_complete'" in course_js

    def test_outline_and_lightbox_events(self):
        assert "'course_outline_open'" in _COURSE_PLAYER_JS
        assert "'course_lightbox_open'" in _COURSE_PLAYER_JS

    def test_no_ga_events_on_timers(self):
        """gtag calls must not live inside setInterval/setTimeout callbacks."""
        for chunk in re.findall(r'setInterval\([^;]*\)|setTimeout\(function\(\)\{[^}]*\}',
                                _COURSE_PLAYER_JS):
            assert 'gtag' not in chunk


# ── Gate safety contract (must not break) ────────────────────


class TestGateContract:
    def test_gate_markup_intact(self, lesson_html):
        assert 'id="gg-course-gate"' in lesson_html
        assert 'id="gg-course-verify-form"' in lesson_html
        assert 'id="gg-course-gate-buy"' in lesson_html
        assert 'id="gg-course-gate-verify"' in lesson_html
        assert 'name="website"' in lesson_html  # honeypot

    def test_unlock_flow_intact(self, course_js):
        assert "getElementById('gg-course-gate')" in course_js
        assert "getElementById('gg-course-lesson')" in course_js
        assert "classList.add('gg-course-unlocked')" in course_js
        assert "WORKER_URL+'/verify'" in course_js

    def test_lesson_hidden_until_unlocked(self, course_css):
        assert '.gg-course-lesson{display:none}' in course_css.replace('{{', '{')

    def test_no_inline_handlers(self, lesson_html, landing_html):
        assert 'onclick=' not in lesson_html
        assert 'onsubmit=' not in lesson_html
        assert 'onclick=' not in landing_html


# ── Landing page upgrades ────────────────────────────────────


class TestLanding:
    def test_lock_icons_on_lessons(self, landing_html):
        assert 'gg-course-lesson-lock' in landing_html
        assert '&#128274;' in landing_html

    def test_instructor_section(self, landing_html):
        assert 'YOUR INSTRUCTOR' in landing_html
        assert 'Matti Rowe' in landing_html

    def test_bundle_strip(self, landing_html):
        assert 'gg-course-bundle' in landing_html
        assert 'BUNDLE' in landing_html
        assert 'href="https://gravelgodcycling.com/course/"' in landing_html

    def test_bundle_strip_names_other_course(self, landing_html):
        assert 'Gravel Hydration Mastery' in landing_html

    def test_no_bundle_strip_with_single_course(self, dirt_craft):
        html = build_landing_page(dirt_craft, all_courses=[dirt_craft])
        assert 'class="gg-course-bundle"' not in html
        from generate_courses import build_bundle_strip
        assert build_bundle_strip(dirt_craft, [dirt_craft]) == ""

    def test_typography_rhythm(self, course_css):
        css = course_css.replace('{{', '{').replace('}}', '}')
        assert '.gg-course-lesson-body p{font-size:17px;line-height:1.7}' in css
        assert 'margin-bottom:30px' in css


# ── Rise blocks v2: labeled graphic, sorting, continue gate, FIB/matching ──


from generate_courses import _COURSE_BLOCKS_V2_JS  # noqa: E402


@pytest.fixture(scope="module")
def l01_html(dirt_craft):
    flat = generate_courses.get_flat_lessons(dirt_craft)
    by_id = {l["id"]: (i, m, l) for i, (m, l) in enumerate(flat)}
    idx, module, lesson = by_id["letting-go"]
    return build_lesson_page(dirt_craft, module, lesson, idx, len(flat), flat)


@pytest.fixture(scope="module")
def l01_markup(l01_html):
    """L01 page with inline <style>/<script> stripped — markup only, so
    progressive-enhancement assertions don't match CSS/JS source text."""
    markup = re.sub(r'<style>.*?</style>', '', l01_html, flags=re.S)
    return re.sub(r'<script[^>]*>.*?</script>', '', markup, flags=re.S)


class TestLabeledGraphicJS:
    def test_in_animation_allowlist(self):
        m = re.search(r'NON_TEXT_BLOCKS=\[(.*?)\]', _COURSE_PLAYER_JS, re.S)
        assert m and "'.gg-guide-labeled-graphic'" in m.group(1)
        assert "'.gg-guide-sorting'" in m.group(1)

    def test_js_flips_markers_and_fallback(self):
        assert "classList.add('gg-lg-ready')" in _COURSE_BLOCKS_V2_JS

    def test_popover_built_with_textcontent(self):
        assert "createElement('div')" in _COURSE_BLOCKS_V2_JS
        assert ".textContent=" in _COURSE_BLOCKS_V2_JS
        assert "innerHTML" not in _COURSE_BLOCKS_V2_JS

    def test_popover_keyboard_and_dismissal(self):
        assert "e.key==='Escape'" in _COURSE_BLOCKS_V2_JS
        assert "pop.focus()" in _COURSE_BLOCKS_V2_JS
        assert "openMarker.focus()" in _COURSE_BLOCKS_V2_JS
        assert "aria-expanded" in _COURSE_BLOCKS_V2_JS

    def test_popover_flips_by_quadrant(self):
        assert "pop.style.right=" in _COURSE_BLOCKS_V2_JS
        assert "pop.style.left=" in _COURSE_BLOCKS_V2_JS
        assert "pop.style.bottom=" in _COURSE_BLOCKS_V2_JS

    def test_marker_pulse_reduced_motion_guarded(self, course_css):
        css = course_css
        kf = css.find('@keyframes gg-lg-pulse')
        assert kf != -1
        last_media = css.rfind('@media', 0, kf)
        assert 'prefers-reduced-motion:no-preference' in css[last_media:kf]

    def test_marker_min_touch_target(self, course_css):
        assert 'min-width:32px' in course_css
        assert 'min-height:32px' in course_css

    @V2_CONTENT_SKIP
    def test_markers_hidden_fallback_visible_without_js(self, l01_markup, course_css):
        """PE contract: server HTML never carries the JS-ready class; CSS
        hides markers (interactive-only) and shows the fallback list by
        default."""
        assert 'gg-lg-ready' not in l01_markup
        assert 'gg-guide-lg-fallback' in l01_markup
        assert '.gg-guide-lg-marker{display:none' in course_css
        assert '.gg-lg-ready .gg-guide-lg-marker{display:flex}' in course_css


class TestSortingJS:
    def test_tap_to_sort_not_drag(self):
        assert 'gg-guide-sorting-cat' in _COURSE_BLOCKS_V2_JS
        assert 'dragstart' not in _COURSE_BLOCKS_V2_JS
        assert 'ondrop' not in _COURSE_BLOCKS_V2_JS

    def test_fly_and_shake_reduced_motion_guarded_in_js(self):
        assert "REDUCED?'gg-sorting-correct':'gg-sorting-fly'" in _COURSE_BLOCKS_V2_JS
        assert "if(!REDUCED) card.classList.add('gg-sorting-shake')" in _COURSE_BLOCKS_V2_JS

    def test_fly_and_shake_keyframes_guarded_in_css(self, course_css):
        for kf_name in ('gg-sorting-fly', 'gg-sorting-shake'):
            kf = course_css.find(f'@keyframes {kf_name}')
            assert kf != -1, f"@keyframes {kf_name} missing"
            last_media = course_css.rfind('@media', 0, kf)
            assert 'prefers-reduced-motion:no-preference' in course_css[last_media:kf]

    def test_wrong_answer_red_flash_always(self):
        assert "card.classList.add('gg-sorting-wrong')" in _COURSE_BLOCKS_V2_JS

    def test_completion_summary_and_single_xp_award(self):
        assert "' / '+total+' sorted" in _COURSE_BLOCKS_V2_JS
        # XP single-award guard: answered map checked before any award
        assert "if(answered[hash]) return;" in _COURSE_BLOCKS_V2_JS
        assert "gg-kc-answered" in _COURSE_BLOCKS_V2_JS
        # restored state must NOT re-award (finish(false))
        assert "finish(false)" in _COURSE_BLOCKS_V2_JS

    def test_emits_block_complete(self):
        assert "gg-block-complete" in _COURSE_BLOCKS_V2_JS


class TestContinueGateJS:
    @V2_CONTENT_SKIP
    def test_content_not_hidden_in_static_html(self, l01_markup):
        """With JS off nothing is hidden: the wrapper/hiding classes are JS
        creations only — they must never appear in the server markup
        (CSS/JS stripped)."""
        assert 'gg-guide-continue-gate' in l01_markup
        assert 'gg-gate-wrap' not in l01_markup
        assert 'gg-gate-closed' not in l01_markup
        # the gate button is not server-disabled
        m = re.search(r'<button[^>]*gg-guide-continue-btn[^>]*>', l01_markup)
        assert m and 'disabled' not in m.group(0)
        # the gated content (commitment) is present and unhidden
        assert 'YOUR COMMITMENT' in l01_markup

    def test_js_creates_wrapper_with_aria_hidden(self):
        assert "wrap.className='gg-gate-wrap gg-gate-closed'" in _COURSE_BLOCKS_V2_JS
        assert "wrap.setAttribute('aria-hidden','true')" in _COURSE_BLOCKS_V2_JS
        assert "wrap.removeAttribute('aria-hidden')" in _COURSE_BLOCKS_V2_JS

    def test_modes_supported(self):
        assert "mode==='none'" in _COURSE_BLOCKS_V2_JS
        assert "mode==='block_above'" in _COURSE_BLOCKS_V2_JS

    def test_disabled_button_shows_hint(self):
        assert "btn.disabled=!ok" in _COURSE_BLOCKS_V2_JS
        assert "Answer the check above to continue" in _COURSE_BLOCKS_V2_JS

    def test_gates_persist_in_course_state(self):
        assert "c.gates=c.gates||{};" in _COURSE_BLOCKS_V2_JS
        assert "localStorage.setItem(LS_KEY" in _COURSE_BLOCKS_V2_JS

    def test_never_gates_on_commitments_or_plain_buttons(self):
        m = re.search(r"var GATEABLE='([^']+)'", _COURSE_BLOCKS_V2_JS)
        assert m
        assert 'commitment' not in m.group(1)
        assert 'callout' not in m.group(1)
        assert 'btn' not in m.group(1)

    def test_completion_events_emitted_by_existing_blocks(self, course_js):
        # multiple-choice KC + accordion (f-string module) and stepper
        assert course_js.count("gg-block-complete") >= 4
        assert "tool.ggStepperDone=true" in _COURSE_PLAYER_JS

    def test_gate_open_animation_reduced_motion_guarded(self):
        assert "if(REDUCED){" in _COURSE_BLOCKS_V2_JS
        m = re.search(r"if\(REDUCED\)\{\s*wrap\.classList\.remove\('gg-gate-closed'\)",
                      _COURSE_BLOCKS_V2_JS)
        assert m, "reduced motion must reveal instantly (no max-height animation)"


class TestKCFormatsJS:
    def test_fib_trims_and_case_insensitive(self):
        assert "input.value.trim()" in _COURSE_BLOCKS_V2_JS
        assert "v.toLowerCase()===a.toLowerCase()" in _COURSE_BLOCKS_V2_JS
        assert "caseSensitive?v===a:" in _COURSE_BLOCKS_V2_JS

    def test_fib_shake_reduced_motion_guarded(self):
        assert "if(!REDUCED) input.classList.add('gg-kc-shake')" in _COURSE_BLOCKS_V2_JS

    def test_matching_tap_to_pair_lock_and_flash(self):
        assert "gg-kc-match-locked" in _COURSE_BLOCKS_V2_JS
        assert "gg-kc-match-wrong" in _COURSE_BLOCKS_V2_JS
        assert "if(!REDUCED) o.classList.add('gg-kc-flash')" in _COURSE_BLOCKS_V2_JS

    def test_both_award_xp_once_via_kc_endpoint(self):
        assert "WORKER_URL+'/kc'" in _COURSE_BLOCKS_V2_JS
        # the shared awardXP guard is the single award path
        assert _COURSE_BLOCKS_V2_JS.count("function awardXP") == 1

    def test_existing_mc_behavior_not_regressed(self, course_js):
        # the original multiple-choice handler is untouched
        assert ".gg-guide-kc-option" in course_js
        assert "data-correct" in course_js
        assert "gg-kc-opt-correct" in course_js
