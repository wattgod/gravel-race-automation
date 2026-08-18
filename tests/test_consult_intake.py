"""Tests for the Gravel God consulting intake form generator (/consulting/intake/)."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path so we can import the generator
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_consult_intake import (
    CONSULT_INTAKE_API,
    build_nav,
    build_header,
    build_fields,
    build_submit_buttons,
    build_success_state,
    build_privacy,
    build_footer,
    build_jsonld,
    build_intake_css,
    build_intake_js,
    generate_intake_page,
)
from generate_consulting import PRIVACY_SENTENCE


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def intake_html():
    return generate_intake_page()


@pytest.fixture(scope="module")
def intake_css():
    return build_intake_css()


@pytest.fixture(scope="module")
def intake_js():
    return build_intake_js()


# ── Page Generation ──────────────────────────────────────────


class TestPageGeneration:
    def test_returns_html(self, intake_html):
        assert isinstance(intake_html, str)
        assert "<!DOCTYPE html>" in intake_html

    def test_has_canonical(self, intake_html):
        assert 'rel="canonical"' in intake_html
        assert "/consulting/intake/" in intake_html

    def test_has_ga4(self, intake_html):
        assert "G-EJJZ9T6M52" in intake_html
        assert "googletagmanager.com" in intake_html

    def test_has_meta_robots_noindex(self, intake_html):
        assert 'name="robots"' in intake_html
        assert "noindex" in intake_html

    def test_has_meta_description(self, intake_html):
        assert 'name="description"' in intake_html

    def test_has_title(self, intake_html):
        assert "<title>" in intake_html
        assert "Consulting Intake" in intake_html

    def test_has_jsonld(self, intake_html):
        assert 'application/ld+json' in intake_html


# ── Nav ──────────────────────────────────────────────────────


class TestNav:
    def test_breadcrumb(self, intake_html):
        assert "gg-breadcrumb" in intake_html
        assert "Consulting" in intake_html
        assert "Intake" in intake_html

    def test_breadcrumb_links_to_consulting(self, intake_html):
        assert 'href="https://gravelgodcycling.com/consulting/"' in intake_html


# ── Fields (14 questions, exact keys) ────────────────────────


class TestFields:
    EXPECTED_FIELD_NAMES = [
        "goal_event",
        "goal_date",
        "hours_typical",
        "hours_max",
        "years_training",
        "ftp",
        "lthr",
        "top_question",
        "whats_gone_wrong",
        "injuries_limits",
        "tp_email",
        "power_meter",
        "hr_strap",
        "coaching_history",
        "anything_else",
    ]

    def test_all_field_names_present(self):
        fields = build_fields()
        for name in self.EXPECTED_FIELD_NAMES:
            assert f'name="{name}"' in fields, f"Missing field: {name}"

    def test_field_count_in_range(self):
        """Spec: 12-14 field GROUPS (goal event + date count as one group)."""
        fields = build_fields()
        names = set(re.findall(r'name="(\w+)"', fields))
        # goal_event + goal_date are one conceptual group in the spec
        group_count = len(names) - 1
        assert 12 <= group_count <= 14, f"Expected 12-14 field groups, got {group_count}"

    def test_tp_email_field_key_exact(self):
        """The TrainingPeaks login email field key MUST be tp_email."""
        fields = build_fields()
        assert 'name="tp_email"' in fields

    def test_tp_email_allows_no_tp(self):
        fields = build_fields()
        assert "no TP" in fields

    def test_ftp_lthr_allow_dont_know(self):
        fields = build_fields()
        assert "don't know" in fields
        assert fields.count("don't know") >= 2

    def test_power_meter_and_hr_strap_are_yes_no(self):
        fields = build_fields()
        assert 'name="power_meter" value="yes"' in fields
        assert 'name="power_meter" value="no"' in fields
        assert 'name="hr_strap" value="yes"' in fields
        assert 'name="hr_strap" value="no"' in fields

    def test_top_question_field(self):
        fields = build_fields()
        assert 'name="top_question"' in fields
        assert "<textarea" in fields

    def test_fields_in_full_page(self, intake_html):
        for name in self.EXPECTED_FIELD_NAMES:
            assert f'name="{name}"' in intake_html


# ── Header / Copy ─────────────────────────────────────────────


class TestHeader:
    def test_header_present(self):
        header = build_header()
        assert "Twelve Questions" in header
        assert "five minutes" in header.lower() or "Five minutes" in header

    def test_missing_token_banner_present(self):
        """Page must handle a missing token with a friendly instruction."""
        header = build_header()
        assert "welcome email" in header.lower()
        assert 'id="token-banner"' in header


# ── Honeypot / Form Structure ─────────────────────────────────


class TestFormStructure:
    def test_honeypot(self, intake_html):
        assert "gg-intake-honeypot" in intake_html
        assert 'name="_honeypot"' in intake_html

    def test_form_element(self, intake_html):
        assert '<form id="intake-form"' in intake_html

    def test_submit_and_save_buttons(self):
        buttons = build_submit_buttons()
        assert 'id="submit-btn"' in buttons
        assert 'id="save-btn"' in buttons
        assert "Save Progress" in buttons


# ── Success State ─────────────────────────────────────────────


class TestSuccessState:
    def test_success_copy(self):
        success = build_success_state()
        assert "I&rsquo;ll have your read done before we talk" in success

    def test_success_hidden_by_default(self):
        success = build_success_state()
        assert 'style="display:none"' in success


# ── Privacy ────────────────────────────────────────────────────


class TestPrivacy:
    def test_privacy_sentence_present(self):
        privacy = build_privacy()
        assert "deleted on request" in privacy

    def test_privacy_matches_consulting_page(self):
        """Privacy language must match the /consulting/ page verbatim."""
        privacy = build_privacy()
        assert PRIVACY_SENTENCE in privacy

    def test_privacy_in_full_page(self, intake_html):
        assert "deleted on request" in intake_html


# ── Fragment Parsing (never query string) ─────────────────────


class TestFragmentParsing:
    def test_reads_hash_not_search(self, intake_js):
        assert "window.location.hash" in intake_js

    def test_does_not_read_query_string_for_token(self, intake_js):
        """The intake token must never be read from window.location.search —
        query strings get logged by servers and leak via referrer headers."""
        assert "location.search" not in intake_js

    def test_no_query_string_token_anywhere(self, intake_html):
        """No `?t=` pattern anywhere in the page — the token is fragment-only."""
        assert "?t=" not in intake_html

    def test_ref_and_t_parsed(self, intake_js):
        assert 'params.get("ref")' in intake_js
        assert 'params.get("t")' in intake_js


# ── Submission (POST, token in body) ──────────────────────────


class TestSubmission:
    def test_posts_to_consult_intake_api(self, intake_js):
        assert CONSULT_INTAKE_API in intake_js
        assert "/api/consult-intake" in intake_js

    def test_payload_shape(self, intake_js):
        assert "ref: frag.ref" in intake_js
        assert "t: frag.t" in intake_js
        assert "answers: answers" in intake_js

    def test_uses_post_method(self, intake_js):
        assert 'method: "POST"' in intake_js

    def test_token_in_body_not_header_or_query(self, intake_js):
        """CORS: token travels in the JSON body, not a custom header or query param."""
        assert "Authorization" not in intake_js
        assert "X-Token" not in intake_js


# ── Save / Resume ──────────────────────────────────────────────


class TestSaveResume:
    def test_localstorage_save(self, intake_js):
        assert "localStorage.setItem" in intake_js
        assert "consult_intake_progress" in intake_js

    def test_localstorage_restore(self, intake_js):
        assert "restoreProgress" in intake_js
        assert "localStorage.getItem" in intake_js

    def test_success_clears_draft(self, intake_js):
        """Only a successful submission clears the saved draft."""
        assert "localStorage.removeItem" in intake_js

    def test_error_keeps_draft(self, intake_js):
        """On a failed submission, the draft must NOT be cleared — the error
        handler must not call removeItem."""
        catch_match = re.search(r'\.catch\(function\(err\)\{(.*?)\}\);', intake_js, re.DOTALL)
        assert catch_match, "Could not find .catch() error handler"
        assert "localStorage.removeItem" not in catch_match.group(1)
        assert "saved on this device" in catch_match.group(1)


# ── Brand Compliance ─────────────────────────────────────────


class TestBrandCompliance:
    def test_no_hardcoded_hex(self, intake_css):
        css_content = intake_css.replace("<style>", "").replace("</style>", "")
        hex_pattern = re.compile(r'(?<![\w-])#[0-9a-fA-F]{3,8}\b')
        matches = hex_pattern.findall(css_content)
        assert matches == [], f"Found hardcoded hex colors: {matches}"

    def test_no_border_radius(self, intake_css):
        assert "border-radius" not in intake_css

    def test_no_box_shadow(self, intake_css):
        assert "box-shadow" not in intake_css

    def test_no_bounce_easing(self, intake_css):
        assert "bounce" not in intake_css.lower()
        assert "spring" not in intake_css.lower()

    def test_no_entrance_animations(self, intake_css):
        assert "@keyframes" not in intake_css

    def test_no_opacity_transition(self, intake_css):
        assert "transition: opacity" not in intake_css
        assert "transition:opacity" not in intake_css

    def test_uses_brand_tokens(self, intake_css):
        assert "var(--gg-color-" in intake_css
        assert "var(--gg-font-" in intake_css

    def test_responsive_breakpoint(self, intake_css):
        assert "600px" in intake_css or "768px" in intake_css

    def test_correct_class_prefix(self, intake_css):
        classes = re.findall(r'\.(gg-[a-z][a-z0-9-]*)', intake_css)
        for cls in classes:
            assert cls.startswith('gg-intake-'), f"Non-prefixed class: .{cls}"


# ── Tokens Are Real ────────────────────────────────────────────


class TestCssTokenValidation:
    def test_all_var_refs_defined(self, intake_css):
        tokens_path = Path(__file__).parent.parent.parent / "gravel-god-brand" / "tokens" / "tokens.css"
        if not tokens_path.exists():
            pytest.skip("Brand tokens not found")
        tokens_css = tokens_path.read_text()
        var_refs = set(re.findall(r'var\((--gg-[a-z0-9-]+)\)', intake_css))
        assert var_refs, "No var(--gg-*) references found — did the generator change?"
        for var_name in var_refs:
            assert var_name in tokens_css, f"Undefined token: {var_name}"


# ── JS Syntax ────────────────────────────────────────────────


class TestJSSyntax:
    def test_js_parses_via_node(self, intake_js):
        js = intake_js.replace("<script>", "").replace("</script>", "")
        result = subprocess.run(
            ["node", "-e", f"new Function({repr(js)})"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"JS syntax error: {result.stderr}"


# ── Footer ───────────────────────────────────────────────────


class TestFooter:
    def test_footer_present(self, intake_html):
        assert "gg-mega-footer" in intake_html
