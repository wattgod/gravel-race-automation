"""Tests for Mission Control dashboard generator."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_mission_control import (
    build_content_pipeline,
    build_data_freshness,
    build_deploy_map,
    build_health_hero,
    build_mc_css,
    build_mc_js,
    build_quick_commands,
    build_seo_pulse,
    build_sprint_log,
    collect_content_pipeline,
    collect_data_freshness,
    collect_deploy_targets,
    collect_health_overview,
    collect_quick_commands,
    collect_seo_pulse,
    collect_sprint_log,
    generate_mc_page,
)


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def mc_html():
    return generate_mc_page()


@pytest.fixture(scope="module")
def mc_css():
    return build_mc_css()


@pytest.fixture(scope="module")
def mc_js():
    return build_mc_js()


# ── Page Generation Tests ────────────────────────────────────────


class TestPageGeneration:
    def test_is_valid_html(self, mc_html):
        assert mc_html.startswith("<!DOCTYPE html>")
        assert "</html>" in mc_html

    def test_has_noindex(self, mc_html):
        assert 'name="robots" content="noindex, nofollow"' in mc_html

    def test_has_title(self, mc_html):
        assert "<title>Mission Control | Gravel God</title>" in mc_html

    def test_has_viewport(self, mc_html):
        assert 'name="viewport"' in mc_html

    def test_has_charset(self, mc_html):
        assert 'charset="utf-8"' in mc_html

    def test_has_tokens_css(self, mc_html):
        assert "--gg-color-" in mc_html

    def test_has_mc_css(self, mc_html):
        assert "gg-mc-" in mc_html

    def test_has_mc_js(self, mc_html):
        assert "gg-mc-copy-btn" in mc_html

    def test_has_all_seven_sections(self, mc_html):
        assert "gg-mc-hero" in mc_html
        assert "Data Freshness" in mc_html
        assert "Content Pipeline" in mc_html
        assert "Deploy Map" in mc_html
        assert "SEO Pulse" in mc_html
        assert "Quick Commands" in mc_html
        assert "Sprint Log" in mc_html

    def test_no_shared_header(self, mc_html):
        """Internal page should not have the public nav."""
        assert "gg-site-nav" not in mc_html

    def test_no_shared_footer(self, mc_html):
        """Internal page should not have the mega footer."""
        assert "gg-mega-footer" not in mc_html


# ── Data Collector Tests ─────────────────────────────────────────


class TestCollectHealthOverview:
    def test_returns_dict(self):
        result = collect_health_overview()
        assert isinstance(result, dict)

    def test_has_expected_keys(self):
        result = collect_health_overview()
        if "error" not in result:
            assert "race_count" in result
            assert "health_score" in result
            assert "gates" in result
            assert "generated_at" in result

    def test_health_score_range(self):
        result = collect_health_overview()
        if "error" not in result:
            assert 0 <= result["health_score"] <= 100

    def test_gates_are_booleans(self):
        result = collect_health_overview()
        if "error" not in result:
            for label, val in result["gates"].items():
                assert isinstance(val, bool), f"Gate {label} should be bool"


class TestCollectDataFreshness:
    def test_returns_dict(self):
        result = collect_data_freshness()
        assert isinstance(result, dict)

    def test_has_expected_keys(self):
        result = collect_data_freshness()
        if "error" not in result:
            for key in ("total", "current_dates", "stale_dates", "tbd_dates",
                        "stubs", "tier_counts", "stale_races"):
                assert key in result, f"Missing key: {key}"

    def test_counts_are_nonnegative(self):
        result = collect_data_freshness()
        if "error" not in result:
            assert result["total"] >= 0
            assert result["stale_dates"] >= 0
            assert result["tbd_dates"] >= 0

    def test_tier_distribution_sums(self):
        result = collect_data_freshness()
        if "error" not in result:
            tier_sum = sum(result["tier_counts"].values())
            assert tier_sum == result["total"], (
                f"Tier sum {tier_sum} != total {result['total']}"
            )

    def test_stale_races_sorted_by_tier(self):
        result = collect_data_freshness()
        if "error" not in result and len(result["stale_races"]) >= 2:
            tier_order = {"T1": 0, "T2": 1, "T3": 2, "T4": 3, "?": 4}
            tiers = [tier_order.get(r["tier"], 4) for r in result["stale_races"]]
            assert tiers == sorted(tiers), "Stale races should be sorted T1 first"


class TestCollectContentPipeline:
    def test_returns_dict(self):
        result = collect_content_pipeline()
        assert isinstance(result, dict)

    def test_finds_generators(self):
        result = collect_content_pipeline()
        if "error" not in result:
            assert result["total_generators"] >= 20, (
                f"Expected 20+ generators, found {result['total_generators']}"
            )

    def test_generators_is_list(self):
        result = collect_content_pipeline()
        if "error" not in result:
            assert isinstance(result["generators"], list)

    def test_output_counts_is_dict(self):
        result = collect_content_pipeline()
        if "error" not in result:
            assert isinstance(result["output_counts"], dict)


class TestCollectDeployTargets:
    def test_returns_dict(self):
        result = collect_deploy_targets()
        assert isinstance(result, dict)

    def test_finds_sync_flags(self):
        result = collect_deploy_targets()
        if "error" not in result:
            assert result["total"] >= 20, (
                f"Expected 20+ sync flags, found {result['total']}"
            )

    def test_flags_start_with_sync(self):
        result = collect_deploy_targets()
        if "error" not in result:
            for flag in result["flags"]:
                assert flag.startswith("--sync-"), f"Flag {flag} should start with --sync-"

    def test_has_categories(self):
        result = collect_deploy_targets()
        if "error" not in result:
            assert "categorized" in result
            assert len(result["categorized"]) >= 3


class TestCollectSeoPulse:
    def test_returns_dict(self):
        result = collect_seo_pulse()
        assert isinstance(result, dict)

    def test_handles_no_snapshots(self):
        result = collect_seo_pulse()
        # Either configured=False or has data — both are valid
        assert "configured" in result or "error" in result or "clicks" in result


class TestCollectQuickCommands:
    def test_returns_dict(self):
        result = collect_quick_commands()
        assert isinstance(result, dict)

    def test_has_groups(self):
        result = collect_quick_commands()
        assert "Generate" in result
        assert "Deploy" in result
        assert "Validate" in result
        assert "Data" in result

    def test_commands_are_tuples(self):
        result = collect_quick_commands()
        for group, commands in result.items():
            for cmd in commands:
                assert len(cmd) == 2, f"Command in {group} should be (cmd, desc) tuple"


class TestCollectSprintLog:
    def test_returns_dict(self):
        result = collect_sprint_log()
        assert isinstance(result, dict)

    def test_has_recent_sprints(self):
        result = collect_sprint_log()
        assert "recent_sprints" in result
        assert len(result["recent_sprints"]) == 3

    def test_has_remaining_work(self):
        result = collect_sprint_log()
        assert "remaining_work" in result
        assert len(result["remaining_work"]) >= 1


# ── Section Builder Tests ────────────────────────────────────────


class TestSectionBuilders:
    def test_health_hero_has_score(self):
        data = {"health_score": 85, "race_count": 328, "generated_at": "2026-02-20 10:00",
                "gates": {"PREFLIGHT": True, "COLORS": True}, "test_ran": False}
        html = build_health_hero(data)
        assert "gg-mc-hero" in html
        assert "85" in html
        assert "328" in html

    def test_health_hero_handles_error(self):
        html = build_health_hero({"error": "test error"})
        assert "gg-mc-error" in html
        assert "test error" in html

    def test_data_freshness_has_metrics(self):
        data = {"total": 328, "current_dates": 280, "stale_dates": 40,
                "tbd_dates": 8, "stubs": 1,
                "tier_counts": {"T1": 25, "T2": 73, "T3": 154, "T4": 76},
                "stale_races": []}
        html = build_data_freshness(data)
        assert "gg-mc-section" in html
        assert "328" in html
        assert "gg-mc-tier-bar" in html

    def test_content_pipeline_shows_generators(self):
        data = {"total_generators": 26, "output_counts": {
            "homepage": {"label": "Homepage", "count": 1, "pattern": "homepage.html"},
            "neo_brutalist": {"label": "Race profiles", "count": 328, "pattern": "race/*/index.html"},
        }}
        html = build_content_pipeline(data)
        assert "26 generators" in html
        assert "Race profiles" in html

    def test_deploy_map_has_copy_buttons(self):
        data = {"total": 5, "categorized": {
            "Content": ["--sync-pages", "--sync-homepage"],
        }}
        html = build_deploy_map(data)
        assert "gg-mc-copy-btn" in html
        assert "--sync-pages" in html

    def test_seo_pulse_unconfigured(self):
        html = build_seo_pulse({"configured": False})
        assert "No GSC data" in html
        assert "gsc_tracker" in html

    def test_seo_pulse_configured(self):
        data = {"configured": True, "snapshot_date": "2026-02-20",
                "clicks": 150, "impressions": 5000, "ctr": 0.03, "position": 15.2,
                "top_queries": [], "top_pages": []}
        html = build_seo_pulse(data)
        assert "150" in html
        assert "15.2" in html

    def test_quick_commands_has_details(self):
        data = collect_quick_commands()
        html = build_quick_commands(data)
        assert "<details" in html
        assert "gg-mc-cmd-group" in html

    def test_sprint_log_has_sprints(self):
        data = collect_sprint_log()
        html = build_sprint_log(data)
        assert "Sprint 38" in html
        assert "Remaining Work" in html


# ── CSS Tests ────────────────────────────────────────────────────


class TestCssTokenCompliance:
    """CSS must use only var(--gg-*) tokens — no raw hex colors."""

    def test_no_raw_hex_in_css(self, mc_css):
        # Extract CSS content between <style> tags
        style_match = re.search(r"<style>(.*?)</style>", mc_css, re.DOTALL)
        assert style_match, "No <style> block found"
        css_content = style_match.group(1)

        # Find hex colors that are NOT inside var() or inside comments
        # Remove comments first
        css_no_comments = re.sub(r"/\*.*?\*/", "", css_content, flags=re.DOTALL)

        hex_matches = re.findall(r"(?<!var\(--gg-color-)#[0-9a-fA-F]{3,8}\b", css_no_comments)
        assert not hex_matches, f"Raw hex colors found in CSS: {hex_matches}"

    def test_uses_gg_color_tokens(self, mc_css):
        assert "var(--gg-color-" in mc_css

    def test_uses_gg_font_tokens(self, mc_css):
        assert "var(--gg-font-" in mc_css

    def test_no_border_radius(self, mc_css):
        assert "border-radius" not in mc_css

    def test_no_box_shadow(self, mc_css):
        assert "box-shadow" not in mc_css

    def test_has_responsive_breakpoint(self, mc_css):
        assert "@media" in mc_css


# ── JS Tests ─────────────────────────────────────────────────────


class TestJsSyntax:
    def test_js_passes_syntax_check(self, mc_js):
        """JS must parse without errors via Node.js."""
        # Extract JS between <script> tags
        script_match = re.search(r"<script>(.*?)</script>", mc_js, re.DOTALL)
        assert script_match, "No <script> block found"
        js_content = script_match.group(1)

        result = subprocess.run(
            ["node", "-e", f"new Function({repr(js_content)})"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"JS syntax error: {result.stderr}"

    def test_has_copy_handler(self, mc_js):
        assert "clipboard" in mc_js

    def test_uses_iife(self, mc_js):
        assert "(function()" in mc_js


# ── Deploy Parity Tests ─────────────────────────────────────────


class TestDeployTargetParity:
    """Verify collected deploy targets match actual push_wordpress.py flags."""

    def test_collected_flags_exist_in_script(self):
        """Every flag we collect should exist in the actual script."""
        result = collect_deploy_targets()
        if result.get("error"):
            pytest.skip("Could not collect deploy targets")

        push_script = Path(__file__).parent.parent / "scripts" / "push_wordpress.py"
        source = push_script.read_text(encoding="utf-8")

        for flag in result["flags"]:
            assert f'"{flag}"' in source, f"Flag {flag} not found in push_wordpress.py"


# ── Health Score Tests ───────────────────────────────────────────


class TestHealthScore:
    def test_perfect_score(self):
        """When everything is good, score should be 100."""
        result = collect_health_overview()
        if result.get("error"):
            pytest.skip("Could not collect health overview")
        # With 328 races, no deduction for low race count
        if result["race_count"] >= 300:
            assert result["health_score"] == 100

    def test_score_is_integer(self):
        result = collect_health_overview()
        if "error" not in result:
            assert isinstance(result["health_score"], int)
