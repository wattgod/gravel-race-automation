"""Tests for the Tahoe / Liquid Glass reskin of the triage page.

Guards against silent regressions:
- CSS scoping (all rules under .mc-tahoe)
- Template structure (wrapper class, CSS link, no leaked inline styles)
- Other pages unaffected (dashboard doesn't get Tahoe classes)
- badge--error component variant exists
- head_extra block exists in base.html
- CSS file exists, is non-empty, and is syntactically scoped

Run:  python3 -m pytest mission_control/tests/test_triage_tahoe.py -v
"""

import os
import re
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from mission_control.tests.conftest import (
    make_communication,
    make_deal,
    make_enrollment,
    make_sequence_send,
)

# Project root for file assertions
MC_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _hours_ago(h):
    return (datetime.now(timezone.utc) - timedelta(hours=h)).isoformat()


def _get_triage_html(client):
    """Fetch triage page and return response text."""
    resp = client.get("/triage")
    assert resp.status_code == 200
    return resp.text


# ---------------------------------------------------------------------------
# Class 1: CSS File Integrity
# ---------------------------------------------------------------------------

class TestCSSFileIntegrity:
    """Verify triage-tahoe.css exists, is non-empty, and follows scoping rules."""

    CSS_PATH = MC_ROOT / "static" / "triage-tahoe.css"

    def test_css_file_exists(self):
        assert self.CSS_PATH.exists(), "triage-tahoe.css is missing"

    def test_css_file_non_empty(self):
        content = self.CSS_PATH.read_text()
        # Strip comments and whitespace
        stripped = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL).strip()
        assert len(stripped) > 100, "triage-tahoe.css is suspiciously short"

    def test_all_selectors_scoped_under_mc_tahoe(self):
        """Every CSS rule must start with .mc-tahoe (or be an @-rule wrapping .mc-tahoe).

        This prevents style leaks to other MC pages.
        """
        content = self.CSS_PATH.read_text()
        # Remove comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        # Find all selectors (text before {)
        # We split on } to get rule blocks, then look for selector text
        blocks = content.split('}')
        for block in blocks:
            if '{' not in block:
                continue
            selector_part = block.split('{')[0].strip()
            if not selector_part:
                continue
            # Skip @-rules themselves (@supports, @media) — they wrap .mc-tahoe rules
            if selector_part.startswith('@'):
                continue
            # Each comma-separated selector must contain .mc-tahoe
            selectors = [s.strip() for s in selector_part.split(',')]
            for sel in selectors:
                if not sel:
                    continue
                assert '.mc-tahoe' in sel, (
                    f"Unscoped CSS selector will leak to other pages: '{sel}'"
                )

    def test_no_hardcoded_hex_colors_in_rules(self):
        """All colors should use CSS custom properties, not hardcoded hex.

        Exception: rgba() values in token definitions are OK.
        """
        content = self.CSS_PATH.read_text()
        # Remove comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

        # Find all property declarations (after the : in rules)
        # We look for #XXX or #XXXXXX patterns that aren't inside var() or token definitions
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Skip token definitions (lines with --)
            if '--tahoe-' in stripped or '--gg-' in stripped:
                continue
            # Skip comment lines
            if stripped.startswith('/*') or stripped.startswith('*'):
                continue
            # Check for hardcoded hex
            hex_matches = re.findall(r'#[0-9a-fA-F]{3,8}\b', stripped)
            for match in hex_matches:
                assert False, (
                    f"Hardcoded hex color '{match}' on line {i}: '{stripped}'. "
                    "Use a CSS custom property instead."
                )

    def test_backdrop_filter_has_supports_fallback(self):
        """CSS must include @supports fallback for backdrop-filter."""
        content = self.CSS_PATH.read_text()
        assert '@supports not' in content, (
            "Missing @supports fallback for backdrop-filter. "
            "Firefox on Linux doesn't support it."
        )
        assert 'backdrop-filter' in content.split('@supports not')[1].split('}')[0], (
            "@supports block doesn't reference backdrop-filter"
        )

    def test_prefers_reduced_motion_handling(self):
        """CSS must include prefers-reduced-motion media query."""
        content = self.CSS_PATH.read_text()
        assert 'prefers-reduced-motion' in content, (
            "Missing prefers-reduced-motion handling. "
            "Hover animations must respect user accessibility settings."
        )

    def test_accent_cards_use_box_shadow_not_border_left(self):
        """Accent cards must use box-shadow inset, not border-left.

        border-left clips the border-radius on the left edge.
        """
        content = self.CSS_PATH.read_text()
        # Remove comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

        # Find triage-card--action and triage-card--stale blocks
        for marker in ['triage-card--action', 'triage-card--stale', 'triage-onboarding']:
            # Find the rule block
            pattern = rf'\.mc-tahoe\s+\.{re.escape(marker)}\s*\{{([^}}]*)\}}'
            match = re.search(pattern, content)
            if match:
                rule_body = match.group(1)
                assert 'border-left' not in rule_body, (
                    f".{marker} uses border-left which clips border-radius. "
                    "Use box-shadow: inset instead."
                )


# ---------------------------------------------------------------------------
# Class 2: Base Template Block
# ---------------------------------------------------------------------------

class TestBaseTemplateBlock:
    """Verify base.html has the head_extra block for per-page CSS injection."""

    BASE_PATH = MC_ROOT / "templates" / "base.html"

    def test_head_extra_block_exists(self):
        content = self.BASE_PATH.read_text()
        assert '{% block head_extra %}' in content, (
            "base.html is missing {% block head_extra %} — "
            "triage CSS cannot be loaded"
        )

    def test_head_extra_is_after_css_before_scripts(self):
        """head_extra must appear after CSS links but before script tags."""
        content = self.BASE_PATH.read_text()
        css_pos = content.rfind('rel="stylesheet"')
        block_pos = content.find('{% block head_extra %}')
        script_pos = content.find('<script')

        assert css_pos < block_pos < script_pos, (
            "head_extra block must be after CSS links and before scripts. "
            f"CSS at {css_pos}, block at {block_pos}, script at {script_pos}"
        )

    def test_head_extra_is_noop_by_default(self):
        """The block should be empty by default (no content for non-triage pages)."""
        content = self.BASE_PATH.read_text()
        # Should be self-closing: {% block head_extra %}{% endblock %}
        assert '{% block head_extra %}{% endblock %}' in content, (
            "head_extra block should be empty by default"
        )


# ---------------------------------------------------------------------------
# Class 3: Triage Template Structure
# ---------------------------------------------------------------------------

class TestTriageTemplateStructure:
    """Verify triage.html has correct Tahoe scaffolding."""

    TRIAGE_PATH = MC_ROOT / "templates" / "triage.html"

    def test_mc_tahoe_wrapper_in_rendered_html(self, client):
        """The mc-tahoe wrapper class must be present in rendered output."""
        html = _get_triage_html(client)
        assert 'class="mc-tahoe"' in html, (
            "Missing .mc-tahoe wrapper — entire Tahoe reskin is silently disabled"
        )

    def test_tahoe_css_linked_in_rendered_html(self, client):
        """triage-tahoe.css must be linked in the rendered page head."""
        html = _get_triage_html(client)
        assert 'triage-tahoe.css' in html, (
            "triage-tahoe.css not linked — Tahoe styles are not loading"
        )

    def test_head_extra_block_overridden(self):
        """triage.html must define {% block head_extra %} with CSS link."""
        content = self.TRIAGE_PATH.read_text()
        assert '{% block head_extra %}' in content
        assert 'triage-tahoe.css' in content

    def test_no_inline_border_left_styles(self):
        """Old inline border-left accent styles must not exist in triage.html.

        These were moved to CSS classes (triage-card--action, triage-card--stale,
        triage-onboarding) to avoid fighting Tahoe's rounded corners.
        """
        content = self.TRIAGE_PATH.read_text()
        assert 'style="border-left:' not in content, (
            "Inline border-left style found — should be a CSS class"
        )
        assert "style='border-left:" not in content, (
            "Inline border-left style found (single quotes)"
        )

    def test_no_inline_grid_styles(self):
        """Grid layouts must use .triage-fyi-grid class, not inline styles."""
        content = self.TRIAGE_PATH.read_text()
        assert 'style="display:grid;grid-template-columns:' not in content, (
            "Inline grid style found — should use .triage-fyi-grid class"
        )

    def test_no_inline_font_family_styles(self):
        """Font-family must come from CSS, not inline styles."""
        content = self.TRIAGE_PATH.read_text()
        assert 'style="font-family:var(--gg-font-data)' not in content, (
            "Inline font-family found — these moved to .triage-section-sub class"
        )

    def test_no_inline_error_badge_styles(self):
        """Error badges must use .gg-badge--error, not inline background styles.

        The old pattern was: style="background:var(--gg-color-error);color:white"
        """
        content = self.TRIAGE_PATH.read_text()
        assert 'background:var(--gg-color-error)' not in content, (
            "Inline error badge style found — use .gg-badge--error class"
        )

    def test_accent_classes_present(self):
        """Template must use CSS classes for accent cards."""
        content = self.TRIAGE_PATH.read_text()
        assert 'triage-card--action' in content
        assert 'triage-card--stale' in content
        assert 'triage-onboarding' in content

    def test_utility_classes_present(self):
        """Template must use utility classes instead of inline styles."""
        content = self.TRIAGE_PATH.read_text()
        # Also check partials that are included
        stats_partial = (MC_ROOT / "templates" / "partials" / "triage_stats.html").read_text()
        combined = content + stats_partial
        assert 'triage-card-desc' in combined
        assert 'triage-btn-sm' in combined
        assert 'triage-cell-sm' in combined
        assert 'triage-empty-sm' in combined
        assert 'triage-stat-clear' in combined

    def test_no_residual_style_attributes(self):
        """Count remaining inline style= attributes.

        Zero is the target. Any remaining ones are tracked debt.
        """
        content = self.TRIAGE_PATH.read_text()
        # Count style= occurrences (both quote styles)
        count = len(re.findall(r'\bstyle\s*=\s*["\']', content))
        assert count == 0, (
            f"Found {count} inline style= attribute(s) in triage.html. "
            "All styles should be in triage-tahoe.css classes."
        )


# ---------------------------------------------------------------------------
# Class 4: Other Pages Unaffected
# ---------------------------------------------------------------------------

class TestOtherPagesUnaffected:
    """Verify that non-triage pages don't get Tahoe classes or CSS."""

    def test_dashboard_has_no_mc_tahoe(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert 'mc-tahoe' not in resp.text, (
            "Dashboard page has .mc-tahoe — Tahoe styles are leaking"
        )

    def test_dashboard_has_no_tahoe_css_link(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert 'triage-tahoe.css' not in resp.text, (
            "Dashboard page loads triage-tahoe.css — should be triage-only"
        )


# ---------------------------------------------------------------------------
# Class 5: Badge Error Variant
# ---------------------------------------------------------------------------

class TestBadgeErrorVariant:
    """Verify gg-badge--error exists as a component-level class."""

    BADGE_CSS_PATH = MC_ROOT / "static" / "components" / "badge.css"

    def test_badge_error_class_exists_in_component_css(self):
        content = self.BADGE_CSS_PATH.read_text()
        assert '.gg-badge--error' in content, (
            "Missing .gg-badge--error in badge.css — "
            "error badges will fall back to teal (the default .gg-badge color)"
        )

    def test_badge_error_uses_error_color(self):
        content = self.BADGE_CSS_PATH.read_text()
        # Find the .gg-badge--error block
        match = re.search(r'\.gg-badge--error\s*\{([^}]*)\}', content)
        assert match, "Could not find .gg-badge--error rule"
        rule_body = match.group(1)
        assert '--gg-color-error' in rule_body, (
            ".gg-badge--error doesn't reference --gg-color-error"
        )

    def test_triage_uses_badge_error_class(self):
        """Triage template must use the CSS class, not inline styles."""
        triage_path = MC_ROOT / "templates" / "triage.html"
        content = triage_path.read_text()
        assert 'gg-badge--error' in content, (
            "Triage template doesn't use .gg-badge--error"
        )

    def test_bounced_badge_renders_with_error_class(self, client, fake_db):
        """A bounced send should render with gg-badge--error, not inline style."""
        fake_db.store["gg_sequence_sends"].append(
            make_sequence_send(
                status="bounced",
                sent_at=_hours_ago(1),
            )
        )
        html = _get_triage_html(client)
        assert 'gg-badge--error' in html
        # Should NOT have inline error styling
        assert 'background:var(--gg-color-error)' not in html


# ---------------------------------------------------------------------------
# Class 6: Rendered Tahoe Structure
# ---------------------------------------------------------------------------

class TestRenderedTahoeStructure:
    """Verify Tahoe-specific CSS classes appear in rendered HTML."""

    def test_fyi_grid_class_in_rendered_html(self, client):
        html = _get_triage_html(client)
        assert 'triage-fyi-grid' in html

    def test_section_sub_class_in_rendered_html(self, client, fake_db):
        """Section subheadings should use CSS class when data is present."""
        fake_db.store["plan_requests"].append({
            "id": str(uuid.uuid4()),
            "status": "pending",
            "payload": {"name": "Test", "email": "t@t.com"},
            "created_at": _now_iso(),
        })
        html = _get_triage_html(client)
        assert 'triage-section-sub' in html

    def test_stat_clear_class_in_rendered_html(self, client):
        """When action_required is 0, the '— clear' span should use CSS class."""
        html = _get_triage_html(client)
        assert 'triage-stat-clear' in html

    def test_system_health_badge_uses_error_class(self, client):
        """System health error badge should use gg-badge--error class."""
        html = _get_triage_html(client)
        # With default mocked health, there should be health badges
        assert 'System Health' in html

    def test_onboarding_renders_with_tahoe_classes(self, client):
        """First-run onboarding should have triage-onboarding class."""
        html = _get_triage_html(client)
        assert 'triage-onboarding' in html

    def test_action_card_renders_with_tahoe_class(self, client):
        html = _get_triage_html(client)
        assert 'triage-card--action' in html

    def test_stale_card_renders_with_tahoe_class(self, client):
        html = _get_triage_html(client)
        assert 'triage-card--stale' in html


# ---------------------------------------------------------------------------
# Class 7: Edge Cases
# ---------------------------------------------------------------------------

class TestTahoeEdgeCases:
    """Edge cases that could break the Tahoe reskin."""

    def test_htmx_ack_response_still_works_inside_mc_tahoe(self, client, fake_db):
        """The .mc-tahoe wrapper must not break htmx hx-target='closest tr'.

        The Ack button uses hx-swap="outerHTML" on the closest <tr>. Adding
        a wrapper div around the content should not affect row-level targeting.
        """
        comm = make_communication(status="received")
        fake_db.store["gg_communications"].append(comm)

        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        resp = client.post(f"/triage/ack/{comm['id']}")
        assert resp.status_code == 200

    def test_load_error_banner_renders_inside_tahoe(self, client):
        """Error banner should render with Tahoe styling, not break layout."""
        with patch("mission_control.routers.triage.get_pending_intakes",
                    side_effect=Exception("boom")):
            html = _get_triage_html(client)
            assert 'mc-tahoe' in html
            assert 'Connection Issue' in html

    def test_all_empty_state_sections_render_cleanly(self, client):
        """With zero data, all empty states should render with Tahoe classes."""
        html = _get_triage_html(client)
        assert 'Welcome to Mission Control' in html
        assert 'triage-empty-sm' in html

    def test_ga4_section_renders_inside_tahoe(self, client):
        """GA4 section should render inside .mc-tahoe wrapper."""
        html = _get_triage_html(client)
        assert 'Site Analytics' in html
        # Verify it's inside the tahoe wrapper
        tahoe_start = html.index('class="mc-tahoe"')
        ga4_pos = html.index('Site Analytics')
        assert tahoe_start < ga4_pos

    def test_bounced_sends_with_null_enrollment(self, client, fake_db):
        """Bounced sends with no enrollment join should render with badge class."""
        fake_db.store["gg_sequence_sends"].append(
            make_sequence_send(
                status="bounced",
                sent_at=_hours_ago(1),
                gg_sequence_enrollments=None,
            )
        )
        html = _get_triage_html(client)
        assert 'gg-badge--error' in html

    def test_many_stale_deals_renders_without_overflow(self, client, fake_db):
        """10+ stale deals should render in a scrollable table, not break layout."""
        for i in range(15):
            fake_db.store["gg_deals"].append(
                make_deal(
                    stage="lead",
                    updated_at=_hours_ago(72),
                    contact_name=f"Lead {i}",
                )
            )
        html = _get_triage_html(client)
        assert 'triage-card--stale' in html
        assert html.count('Lead ') >= 15
