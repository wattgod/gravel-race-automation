"""Tests for the Gravel God coaching page generator.

Rebuilt 2026-11-15 as "Field Notes" (Matti picked mock Opus C, with the
Astra B photo card): hero + ID card (real photo crossfading to the v6.7
cartoon) -> fit -> terms (what you get) -> week -> how-it-works -> tiers
(ledger + 3-question picker) -> faq -> final-cta. This suite describes the
page as it ships now.
"""
from __future__ import annotations

import html
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path so we can import the generator
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_coaching import (
    ID_ROWS,
    IMAGES,
    IMG_OUTPUT_SUBDIR,
    IMG_SRC_DIR,
    LEDGER_GROUPS,
    PICKER_QUESTIONS,
    QUESTIONNAIRE_URL,
    TIER_BLURBS,
    TIERS,
    build_nav,
    build_hero,
    build_id_card,
    build_terms,
    build_week,
    build_how_it_works,
    build_tiers,
    build_fit_check,
    build_honest_check,
    build_faq,
    build_application_close,
    build_footer,
    build_mobile_sticky_cta,
    build_coaching_css,
    build_coaching_js,
    build_jsonld,
    generate_coaching_page,
    write_coaching_images,
)


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def coaching_html():
    return generate_coaching_page()


@pytest.fixture(scope="module")
def coaching_css():
    return build_coaching_css()


@pytest.fixture(scope="module")
def coaching_js():
    return build_coaching_js()


# ── Page Generation ──────────────────────────────────────────


class TestPageGeneration:
    def test_returns_html(self, coaching_html):
        assert isinstance(coaching_html, str)
        assert "<!DOCTYPE html>" in coaching_html

    def test_has_canonical(self, coaching_html):
        assert 'rel="canonical"' in coaching_html
        assert "/coaching/" in coaching_html

    def test_has_ga4(self, coaching_html):
        assert "G-EJJZ9T6M52" in coaching_html
        assert "googletagmanager.com" in coaching_html

    def test_has_ab_snippet(self, coaching_html):
        assert "dataLayer" in coaching_html

    def test_has_jsonld(self, coaching_html):
        assert 'application/ld+json' in coaching_html
        assert '"@type":"WebPage"' in coaching_html
        assert '"@type":"Service"' in coaching_html

    def test_has_meta_robots(self, coaching_html):
        assert 'name="robots"' in coaching_html
        assert 'content="index, follow"' in coaching_html

    def test_has_meta_description(self, coaching_html):
        assert 'name="description"' in coaching_html

    def test_has_og_tags(self, coaching_html):
        assert 'og:title' in coaching_html
        assert 'og:description' in coaching_html

    def test_has_title(self, coaching_html):
        assert "<title>" in coaching_html
        assert "Coaching" in coaching_html


# ── Nav ──────────────────────────────────────────────────────


class TestNav:
    def test_nav_links(self, coaching_html):
        assert "/coaching/" in coaching_html
        assert "/about/" in coaching_html
        assert ">SERVICES</a>" in coaching_html
        assert ">ABOUT</a>" in coaching_html

    def test_breadcrumb(self, coaching_html):
        assert "gg-breadcrumb" in coaching_html
        assert "Coaching" in coaching_html

    def test_current_page_marker(self, coaching_html):
        assert 'aria-current="page"' in coaching_html
        assert 'aria-current="page">SERVICES</a>' in coaching_html


# ── Hero — "The Dossier" hero with corner CTA ───────────────



# ── Hero + ID card ───────────────────────────────────────────


class TestHero:
    def test_hero_id_and_cta(self):
        hero = build_hero()
        assert 'id="hero"' in hero
        assert f'href="{QUESTIONNAIRE_URL}"' in hero
        assert 'data-cta="hero_apply"' in hero
        assert "APPLY FOR COACHING &rarr;" in hero

    def test_headline_visible_text(self, coaching_html):
        h1 = re.search(r"<h1>(.*?)</h1>", coaching_html, re.DOTALL).group(1)
        text = re.sub(r"<[^>]+>", "", h1)
        assert text == "Gravel coaching for people who want to throw down but still like to get down."

    def test_highlights(self):
        hero = build_hero()
        assert "<mark>throw down</mark>" in hero
        assert "<mark>get down.</mark>" in hero

    def test_subhead(self):
        hero = build_hero()
        assert "Three levels, from a weekly look at your training to every file read the day it lands." in hero
        assert "<strong>$199 to $1,200</strong> every 4 weeks." in hero


class TestIdCard:
    def test_bio_line_verbatim(self):
        """Matti, 2026-11-15: the bio line, word for word."""
        card = build_id_card()
        assert "I&#39;m Matti Rowe. Peddler of bikes and hot takes, and really fast clients." in card

    def test_resume_rows(self):
        card = build_id_card()
        for label, value in ID_ROWS:
            assert f"<span>{label}</span>{value}" in card

    def test_talent_line(self):
        """Matti asked the resume to say very few have gotten farther on less talent."""
        values = " ".join(v for _l, v in ID_ROWS)
        assert "Very few people have gotten farther on less of it." in values

    def test_only_public_facts(self):
        values = " ".join(v for _l, v in ID_ROWS)
        for fact in ("12 years at TrainingPeaks", "Cat 1", "NRC", "Rio Grande Elite",
                     "third kid", "Unbound 200", "SBT GRVL", "Red Granite Grinder in 2021 and 2022"):
            assert fact in values

    def test_photo_and_cartoon(self):
        card = build_id_card()
        photo, pw, ph = IMAGES["photo"]
        toon, tw, th = IMAGES["cartoon"]
        assert f'src="/coaching/img/{photo}"' in card
        assert f'width="{pw}" height="{ph}"' in card
        assert f'src="/coaching/img/{toon}"' in card
        assert 'class="gg-coach-id-toon"' in card
        # The cartoon repeats the photo, so screen readers hear one picture.
        assert re.search(r'<img class="gg-coach-id-toon"[^>]*alt=""[^>]*aria-hidden="true"', card)
        assert re.search(r'<img class="gg-coach-id-real"[^>]*alt="[^"]+"', card)

    def test_swap_animation_and_reduced_motion(self, coaching_css):
        assert "@keyframes gg-coach-idswap" in coaching_css
        assert "animation: gg-coach-idswap" in coaching_css
        rm = coaching_css.split("prefers-reduced-motion: reduce", 1)[1]
        assert ".gg-coach-id-toon { animation: none; opacity: 0; }" in rm

    def test_photo_preloaded(self, coaching_html):
        assert f'<link rel="preload" as="image" href="/coaching/img/{IMAGES["photo"][0]}">' in coaching_html

    def test_no_reading_applications_line(self, coaching_html):
        """Matti, 2026-11-15: don't say I read every application myself. Of course I do."""
        visible = _visible_text(coaching_html).lower()
        for phrase in ("read every application", "read your application", "read it myself",
                       "i read it and reply", "myself, every time"):
            assert phrase not in visible, phrase


class TestCoachingImages:
    def test_every_image_is_in_the_repo(self):
        for name, w, h in IMAGES.values():
            path = IMG_SRC_DIR / name
            assert path.is_file(), f"missing {path}"
            from PIL import Image
            with Image.open(path) as im:
                assert im.size == (w, h), f"{name} is {im.size}, page says {(w, h)}"

    def test_write_copies_all(self, tmp_path):
        dest = write_coaching_images(tmp_path)
        assert dest == tmp_path / IMG_OUTPUT_SUBDIR
        assert sorted(p.name for p in dest.iterdir()) == sorted(n for n, _w, _h in IMAGES.values())

    def test_missing_image_refuses(self, tmp_path, monkeypatch):
        import generate_coaching
        monkeypatch.setattr(generate_coaching, "IMG_SRC_DIR", tmp_path / "nowhere")
        with pytest.raises(FileNotFoundError):
            generate_coaching.write_coaching_images(tmp_path / "out")


# ── Fit check (is this for me) ───────────────────────────────


class TestFit:
    def test_fit_id_dark_band(self):
        fit = build_honest_check()
        assert 'id="fit"' in fit
        assert "gg-coach-band--dark" in fit

    def test_yes_no_lists(self):
        fit = build_honest_check()
        yes, no = fit.split('class="gg-coach-fit-no"')
        assert yes.count("<li>") == 3
        assert no.count("<li>") == 3
        assert "Coaching fits if" in yes
        assert "Probably not a fit if" in no
        assert "I&#39;m not a doctor or a physio." in no


# ── What you get ─────────────────────────────────────────────


class TestTerms:
    def test_five_items(self):
        terms = build_terms()
        assert 'id="terms"' in terms
        assert terms.count("<li>") == 5
        for t in ("I read your rides.", "A plan for your gravel race.", "Fueling for the long day.",
                  "The week moves when your life does.", "Straight answers."):
            assert f"<h3>{t}</h3>" in terms

    def test_tier_claims_match_inclusions(self):
        terms = build_terms()
        assert "At Min I look once a week. At Max I look the day the file lands." in terms
        assert "At Mid and Max, the week changes that week." in terms


# ── A week with me ───────────────────────────────────────────


class TestWeek:
    def test_rows(self):
        week = build_week()
        assert 'id="week"' in week
        rows = re.findall(r'<th scope="row">([^<]+)</th>', week)
        assert rows == ["Each ride", "Each week", "Life happens", "Strategy calls", "Race week", "The season"]

    def test_phone_labels_follow_tiers(self):
        week = build_week()
        for _k, name, _p in TIERS:
            assert f'data-t="{name.upper()}"' in week

    def test_calls_match_ledger(self):
        week = build_week()
        assert ">Quarterly<" in week and ">Every 4 weeks<" in week


# ── How it works ─────────────────────────────────────────────


class TestHowItWorks:
    def test_five_steps(self):
        how = build_how_it_works()
        assert 'id="how-it-works"' in how
        assert how.count("<li>") == 5

    def test_real_flow(self):
        how = build_how_it_works()
        for bit in ("About 10 min", "2 business days", "a link for your first 4 weeks plus the $99 setup fee",
                    "I set you up on TrainingPeaks"):
            assert bit in how


# ── Levels: ledger + picker ──────────────────────────────────


class TestTiers:
    def test_tiers_id(self):
        assert 'id="tiers"' in build_tiers()

    def test_prices_from_tiers(self):
        tiers = build_tiers()
        for key, name, price in TIERS:
            assert f'data-tier="{key}"' in tiers
            assert f'<span class="gg-coach-tprice">{price}</span>' in tiers
            assert TIER_BLURBS[key] in tiers
        assert tiers.count('<span class="gg-coach-tper">every 4 weeks</span>') == 3

    def test_apply_links(self):
        tiers = build_tiers()
        for key, name, _p in TIERS:
            assert f'href="{QUESTIONNAIRE_URL}?tier={key}"' in tiers
            assert f'data-cta="tier_{key}"' in tiers
            assert f">APPLY FOR {name.upper()}</a>" in tiers

    def test_ledger_rows(self):
        tiers = build_tiers()
        rows = re.findall(r'<th scope="row">([^<]+)</th>', tiers)
        expected = [label for _g, group in LEDGER_GROUPS for label, *_v in group]
        assert rows == expected
        assert len(rows) == 15

    def test_inclusions_are_cumulative(self):
        """Nothing a lower tier gets is missing from a higher one."""
        for _g, group in LEDGER_GROUPS:
            for label, mn, md, mx in group:
                if mn is True:
                    assert md is True and mx is True, label
                if md is True:
                    assert mx is True, label

    def test_setup_fee_and_cancel_fine_print(self):
        tiers = build_tiers()
        assert "$99 one-time setup fee" in tiers
        assert "Any waiver is offered privately, case by case." in tiers
        assert "No cancellation fee." in tiers

    def test_phone_tabs_default_mid(self):
        tiers = build_tiers()
        assert 'data-show="mid"' in tiers
        assert 'data-tab="mid" aria-selected="true"' in tiers
        assert tiers.count('role="tab"') == 3

    def test_no_month_language(self, coaching_html):
        visible = _visible_text(coaching_html).lower()
        for bad in ("monthly", "/mo", "per month", "a month"):
            assert bad not in visible


class TestPicker:
    @pytest.fixture(scope="class")
    def picker(self):
        return build_fit_check()

    def test_hidden_without_js(self, picker):
        assert '<form class="gg-coach-picker" id="gg-coach-picker" aria-label="Three questions to pick a level" hidden>' in picker
        assert 'id="gg-coach-picker-out" aria-live="polite" hidden' in picker

    def test_three_questions_nine_radios(self, picker):
        assert picker.count("<fieldset>") == 3
        assert picker.count('type="radio"') == 9
        for qi, (text, options) in enumerate(PICKER_QUESTIONS, start=1):
            assert f"<p>{text}</p>" in picker
            for opt in options:
                assert f"<span>{opt}</span>" in picker

    def test_js_shows_it(self, coaching_js):
        assert "form.hidden = false;" in coaching_js
        assert "out.hidden = false;" in coaching_js

    def test_scoring_every_combination(self, coaching_js):
        """Rounded mean of the three answers: 1 → min, 2 → mid, 3 → max,
        for all 27 answer sets."""
        js = coaching_js.replace("<script>", "").replace("</script>", "")
        m = re.search(r"var names = (\{[^}]*\});", js)
        assert m
        script = (
            "var names=" + m.group(1) + ";var out=[];"
            "for(var a=1;a<4;a++)for(var b=1;b<4;b++)for(var c=1;c<4;c++)"
            "out.push(names[Math.round((a+b+c)/3)]);console.log(out.join(','));"
        )
        res = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        got = res.stdout.strip().split(",")
        names = {1: "min", 2: "mid", 3: "max"}
        # Three integers over 3 never land on .5, so Python's round agrees with Math.round.
        want = [names[round((a + b + c) / 3)] for a in (1, 2, 3) for b in (1, 2, 3) for c in (1, 2, 3)]
        assert got == want

    def test_result_labels_from_tiers(self, coaching_js):
        for _k, name, price in TIERS:
            assert f"Marked: {name}, {price} every 4 weeks." in coaching_js

    def test_analytics(self, coaching_js):
        assert "coaching_fitcheck_answer" in coaching_js
        assert "coaching_fitcheck_result" in coaching_js


# ── FAQ ──────────────────────────────────────────────────────


class TestFAQ:
    def test_eight_details(self):
        faq = build_faq()
        assert 'id="faq"' in faq
        assert faq.count('<details class="gg-coach-faq-item">') == 8
        assert faq.count("<summary>") == 8

    def test_setup_fee_and_cancel(self):
        faq = build_faq()
        assert "What&#39;s the $99 setup fee?" in faq
        assert "Can I cancel anytime?" in faq

    def test_after_apply(self):
        faq = build_faq()
        assert "You hear back from me within two business days" in faq


# ── Application close ────────────────────────────────────────


class TestApplicationClose:
    def test_close(self):
        close = build_application_close()
        assert 'id="final-cta"' in close
        assert "Start your file." in close
        assert 'data-cta="final_fill_intake"' in close
        assert f'href="{QUESTIONNAIRE_URL}"' in close
        assert 'href="mailto:gravelgodcoaching@gmail.com"' in close

    def test_close_art(self):
        close = build_application_close()
        name, w, h = IMAGES["close"]
        assert f'src="/coaching/img/{name}"' in close
        assert f'width="{w}" height="{h}"' in close


class TestNothingUnbuiltShips:
    def test_no_placeholders(self, coaching_html):
        """The proof slot and capacity line wait on Matti's real words and
        number; nothing stands in for them."""
        visible = _visible_text(coaching_html)
        assert "NOT BUILT" not in visible
        assert "placeholder" not in visible.lower()
        assert coaching_html.count("<blockquote") == 0


class TestMobileStickyCTA:
    def test_label_updated(self):
        sticky = build_mobile_sticky_cta()
        assert "APPLY FOR COACHING &rarr;" in sticky

    def test_data_cta_and_href(self):
        sticky = build_mobile_sticky_cta()
        assert 'data-cta="sticky_cta"' in sticky
        assert f'href="{QUESTIONNAIRE_URL}"' in sticky


SECTION_IDS = ("hero", "fit", "terms", "week", "how-it-works", "tiers", "faq", "final-cta")


# ── Brand Compliance ─────────────────────────────────────────


class TestBrandCompliance:
    def test_no_hardcoded_hex_in_coaching_css(self, coaching_css):
        css = re.sub(r'/\*.*?\*/', '', coaching_css, flags=re.DOTALL)
        hex_colors = re.findall(r'#[0-9a-fA-F]{3,8}\b', css)
        assert len(hex_colors) == 0, f"Found hardcoded hex in coaching CSS: {hex_colors[:5]}"

    def test_no_border_radius(self, coaching_css):
        assert "border-radius" not in coaching_css

    def test_no_box_shadow(self, coaching_css):
        assert "box-shadow" not in coaching_css

    def test_uses_brand_tokens(self, coaching_css):
        assert "var(--gg-color-" in coaching_css
        assert "var(--gg-font-" in coaching_css

    def test_no_bounce_easing(self, coaching_css):
        assert "cubic-bezier(0.34, 1.56" not in coaching_css

    def test_correct_class_prefix(self, coaching_css):
        allowed_roots = (
            'gg-coach-', 'gg-neo-brutalist', 'gg-site-header', 'gg-hero',
            'gg-section', 'gg-breadcrumb', 'gg-footer', 'gg-mega-footer',
            'gg-has-js', 'gg-in-view',
        )
        classes = set(re.findall(r'\.([a-zA-Z][\w-]*)', coaching_css))
        for cls in classes:
            assert cls.startswith(allowed_roots), (
                f"Non-prefixed class in coaching CSS: .{cls}"
            )


class TestTokenValidation:
    @pytest.fixture(scope="class")
    def defined_tokens(self):
        tokens_path = Path(__file__).parent.parent.parent / "gravel-god-brand" / "tokens" / "tokens.css"
        if not tokens_path.exists():
            pytest.skip("tokens.css not found")
        content = tokens_path.read_text()
        return set(re.findall(r'(--gg-[\w-]+)\s*:', content))

    def test_coaching_css_all_var_refs_defined(self, coaching_css, defined_tokens):
        used = set(re.findall(r'var\((--gg-[\w-]+)\)', coaching_css))
        undefined = used - defined_tokens
        assert not undefined, f"Undefined CSS tokens in coaching CSS: {undefined}"


# ── GA4 Events ───────────────────────────────────────────────


class TestGA4Events:
    def test_all_events_present(self, coaching_js):
        events = [
            "coaching_faq_open",
            "coaching_scroll_depth",
            "cta_click",
            "coaching_page_view",
        ]
        for event in events:
            assert event in coaching_js, f"Missing GA4 event: {event}"

    def test_no_carousel_events(self, coaching_js):
        assert "coaching_carousel" not in coaching_js

    def test_scroll_depth_section_ids_match_real_sections(self, coaching_js, coaching_html):
        """Every id referenced by the scroll-depth IIFE must exist in the
        shipped HTML, and the set must be exactly the real content
        sections: no dead ids, no missing sections."""
        section_ids = re.findall(r"id:\s*'([\w-]+)'", coaching_js)
        assert set(section_ids) == set(SECTION_IDS)
        for sid in section_ids:
            assert f'id="{sid}"' in coaching_html, f"Dead section id in scroll-depth JS: {sid}"

    def test_old_section_labels_removed(self, coaching_js):
        for old_id in ("'problem'", "'deliverables'", "'results'", "'honest-check'"):
            assert old_id not in coaching_js, f"Stale scroll-depth id still present: {old_id}"


# ── JS Syntax ────────────────────────────────────────────────


class TestJSSyntax:
    def test_js_parses_via_node(self, coaching_js):
        js_body = coaching_js.replace("<script>", "").replace("</script>", "")
        result = subprocess.run(
            [
                "node", "--input-type=module", "-e",
                "const src = process.argv[1];"
                "new Function(src);"
                "console.log('SYNTAX_OK');",
                js_body,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"JS syntax error: {result.stdout} {result.stderr}"
        assert "SYNTAX_OK" in result.stdout


# ── JSON-LD ──────────────────────────────────────────────────


class TestJSONLD:
    def test_webpage_schema(self):
        ld = build_jsonld()
        assert '"@type":"WebPage"' in ld
        assert "/coaching/" in ld
        assert "Gravel God" in ld

    def test_service_schema(self):
        ld = build_jsonld()
        assert '"@type":"Service"' in ld
        assert "Gravel Race Coaching" in ld

    def test_uses_safe_json_for_script(self):
        """JSON-LD must go through _safe_json_for_script — a '</script>'
        payload should never be able to break out of the <script> tag."""
        from generate_neo_brutalist import _safe_json_for_script
        payload = {"a": "</script><script>alert(1)</script>"}
        safe = _safe_json_for_script(payload)
        assert "</script>" not in safe

    def test_no_raw_json_dumps_regression(self):
        """Regression guard: build_jsonld must not fall back to raw
        json.dumps — that would reopen the </script>-injection hole
        _safe_json_for_script exists to close."""
        import inspect
        from generate_coaching import build_jsonld as _build_jsonld
        source = inspect.getsource(_build_jsonld)
        assert "json.dumps(" not in source


# ── Accessibility ────────────────────────────────────────────


class TestAccessibility:
    def test_skip_to_content_link(self, coaching_html):
        assert 'class="gg-coach-skip-link"' in coaching_html
        assert 'Skip to content' in coaching_html

    def test_reduced_motion_css(self, coaching_css):
        assert "prefers-reduced-motion: reduce" in coaching_css

    def test_faq_uses_native_disclosure(self, coaching_html):
        assert "<details" in coaching_html and "<summary>" in coaching_html
        assert 'role="button"' not in build_faq()

    def test_ledger_marks_have_names(self):
        tiers = build_tiers()
        assert 'role="img" aria-label="Included"' in tiers
        assert 'role="img" aria-label="Not included"' in tiers


# ── Scroll Animations (shared guards) ───────────────────────
# The Dossier itself has no data-animate content — no fade-stagger,
# no entrance animations — but the shared scroll_animations module is
# still wired in for its .gg-has-js / .gg-in-view / IntersectionObserver
# guard contract used sitewide.


class TestScrollAnimationGuards:
    def test_no_data_animate_anywhere(self, coaching_html):
        """The Dossier is a still document — no entrance animations, no
        observer-gated content anywhere on the page. (The shared
        scroll_animations JS still references the bare `[data-animate]`
        selector as part of its generic observer wiring — that's fine;
        what matters is that no element actually carries the attribute.)"""
        assert 'data-animate="' not in coaching_html

    def test_reduced_motion_no_preference_guard(self, coaching_css):
        assert "prefers-reduced-motion: no-preference" in coaching_css

    def test_gg_has_js_in_js(self, coaching_js):
        assert "gg-has-js" in coaching_js

    def test_gg_in_view_in_js(self, coaching_js):
        assert "gg-in-view" in coaching_js

    def test_intersection_observer_in_js(self, coaching_js):
        assert "IntersectionObserver" in coaching_js


# ── Restraint Guard ──────────────────────────────────────────
# The page asserts; it doesn't perform. Banned substrings from the old
# loud template — and from the sibling-brand banned set — must never
# come back.


BANNED_SUBSTRINGS = [
    "$14.95",
    "/ride",
    "If you can pedal",
    "blown race",
    "costs you",
    "suffer smarter",
    "Not a Spreadsheet",
    "generated in 2 seconds",
    "Honest Check",
    "Can't Get From a Prompt",
]

# Checked against VISIBLE TEXT ONLY (script/style stripped, tags stripped) —
# these are generic words that can legitimately appear in class names,
# comments, or CSS without being loud marketing copy on the rendered page.
NEW_BANNED_VISIBLE_TEXT = [
    "unlock",
    "transform",
    "crush",
    "Fitness is common",
    "TERMS OF WORK",
    "COURSES ON FILE",
    "Not a Spreadsheet",
]

COURSE_COUNT_FLEX_PHRASES = [
    "757 courses",
    "757 races",
    "course profiles",
]


def _visible_text(html_doc: str) -> str:
    """Strip <script>...</script> and <style>...</style> blocks, then strip
    remaining HTML tags, leaving only what a reader actually sees."""
    no_script = re.sub(r'<script.*?</script>', '', html_doc, flags=re.DOTALL)
    no_style = re.sub(r'<style.*?</style>', '', no_script, flags=re.DOTALL)
    return re.sub(r'<[^>]+>', '', no_style)


class TestRestraintGuard:
    @pytest.mark.parametrize("phrase", BANNED_SUBSTRINGS)
    def test_banned_phrase_absent(self, coaching_html, phrase):
        assert phrase not in coaching_html, f"Banned phrase found in coaching page: {phrase!r}"

    @pytest.mark.parametrize("phrase", NEW_BANNED_VISIBLE_TEXT)
    def test_banned_visible_text_absent(self, coaching_html, phrase):
        visible = _visible_text(coaching_html)
        assert phrase not in visible, f"Banned word found in visible coaching page text: {phrase!r}"

    @pytest.mark.parametrize("phrase", COURSE_COUNT_FLEX_PHRASES)
    def test_no_course_count_flex_in_visible_text(self, coaching_html, phrase):
        visible = _visible_text(coaching_html)
        assert phrase not in visible, f"Course-count flex phrase in visible text: {phrase!r}"

    def test_no_exclamation_points_in_visible_text(self, coaching_html):
        visible = _visible_text(coaching_html)
        assert "!" not in visible, "Exclamation point found in visible coaching page text"

    def test_no_tire_comparison(self):
        tiers = build_tiers()
        assert "tires" not in tiers.lower()

    def test_no_coffee_cliche(self, coaching_html):
        lower = coaching_html.lower()
        assert "latte" not in lower
        assert "cup of" not in lower

    def test_no_slop_phrases(self, coaching_html):
        from slop_rules import check_text
        findings = check_text(coaching_html, is_html=True)
        assert not findings, f"Slop findings on coaching page: {findings}"

    def test_no_defensive_messaging(self, coaching_html):
        """Never 'no sponsors / not sponsored' framing — plants doubt."""
        lower = coaching_html.lower()
        assert "no sponsors" not in lower
        assert "not sponsored" not in lower
        assert "no affiliates" not in lower


# ── Required Content ─────────────────────────────────────────


class TestRequiredContent:
    def test_link_to_about(self, coaching_html):
        from generate_neo_brutalist import SITE_BASE_URL
        assert f"{SITE_BASE_URL}/about/" in coaching_html

    def test_apply_url_present(self, coaching_html):
        assert QUESTIONNAIRE_URL in coaching_html

    def test_questionnaire_url_shape(self):
        from generate_neo_brutalist import SITE_BASE_URL
        assert QUESTIONNAIRE_URL == f"{SITE_BASE_URL}/coaching/apply/"

    def test_setup_fee(self, coaching_html):
        assert "$99 setup fee" in coaching_html
        assert "includes TrainingPeaks Premium" in coaching_html
        assert "NOSETUP" not in coaching_html

    def test_hero_h1(self, coaching_html):
        assert coaching_html.count("<h1>") == 1
        assert "throw down</mark> but still like to <mark>get down." in coaching_html

    def test_final_contact_line(self, coaching_html):
        assert "gravelgodcoaching@gmail.com" in coaching_html
        assert 'href="mailto:gravelgodcoaching@gmail.com"' in coaching_html

    def test_removed_sections_absent(self, coaching_html):
        for old_id in ("problem", "deliverables", "results", "honest-check"):
            assert f'id="{old_id}"' not in coaching_html

    def test_no_testimonials(self, coaching_html):
        assert coaching_html.count("<blockquote") == 0

    def test_all_section_ids_present(self, coaching_html):
        for sid in SECTION_IDS:
            assert f'id="{sid}"' in coaching_html
