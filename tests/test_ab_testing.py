"""Tests for A/B testing system — config validation, JS syntax, and generator integration."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))

from ab_experiments import EXPERIMENTS, export_config, validate_experiments


# ── Config Validation ────────────────────────────────────────


class TestExperimentConfig:
    def test_no_validation_errors(self):
        errors = validate_experiments()
        assert errors == [], f"Validation errors: {errors}"

    def test_all_have_unique_ids(self):
        ids = [e["id"] for e in EXPERIMENTS]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {ids}"

    def test_all_have_control_variant(self):
        for exp in EXPERIMENTS:
            variant_ids = [v["id"] for v in exp["variants"]]
            assert "control" in variant_ids, f"{exp['id']}: no control variant"

    def test_all_have_at_least_two_variants(self):
        for exp in EXPERIMENTS:
            assert len(exp["variants"]) >= 2, (
                f"{exp['id']}: only {len(exp['variants'])} variant(s)"
            )

    def test_all_have_selectors(self):
        for exp in EXPERIMENTS:
            assert exp.get("selector"), f"{exp['id']}: missing selector"
            assert exp["selector"].startswith("[data-ab="), (
                f"{exp['id']}: selector should use data-ab attribute: {exp['selector']}"
            )

    def test_all_have_pages(self):
        for exp in EXPERIMENTS:
            assert exp.get("pages"), f"{exp['id']}: missing pages"

    def test_traffic_in_range(self):
        for exp in EXPERIMENTS:
            t = exp.get("traffic", 1.0)
            assert 0 < t <= 1.0, f"{exp['id']}: traffic {t} out of range"

    def test_variant_ids_are_valid(self):
        for exp in EXPERIMENTS:
            for v in exp["variants"]:
                assert v["id"], f"{exp['id']}: empty variant id"
                assert v["id"].replace("_", "").isalnum(), (
                    f"{exp['id']}/{v['id']}: invalid chars in variant id"
                )

    def test_variant_content_not_empty(self):
        for exp in EXPERIMENTS:
            for v in exp["variants"]:
                assert v.get("content"), (
                    f"{exp['id']}/{v['id']}: empty content"
                )

    def test_conversion_config(self):
        for exp in EXPERIMENTS:
            conv = exp.get("conversion")
            assert conv, f"{exp['id']}: missing conversion config"
            assert conv.get("type") == "click", (
                f"{exp['id']}: only 'click' conversion type supported"
            )
            assert conv.get("selector"), (
                f"{exp['id']}: missing conversion selector"
            )


# ── Export / JSON ────────────────────────────────────────────


class TestExportConfig:
    def test_export_returns_dict(self):
        config = export_config()
        assert isinstance(config, dict)
        assert "version" in config
        assert "experiments" in config

    def test_exported_experiments_are_active(self):
        config = export_config()
        for exp in config["experiments"]:
            assert exp.get("id")
            assert exp.get("selector")
            assert exp.get("variants")
            assert len(exp["variants"]) >= 2

    def test_export_json_serializable(self):
        config = export_config()
        serialized = json.dumps(config)
        assert serialized
        parsed = json.loads(serialized)
        assert parsed["version"] == config["version"]

    def test_export_omits_internal_fields(self):
        config = export_config()
        for exp in config["experiments"]:
            assert "description" not in exp
            assert "start" not in exp
            assert "end" not in exp


# ── JS Syntax ────────────────────────────────────────────────


class TestJsSyntax:
    def test_ab_tests_js_syntax(self):
        js_file = PROJECT_ROOT / "web" / "gg-ab-tests.js"
        assert js_file.exists(), f"Missing: {js_file}"
        js_code = js_file.read_text()
        result = subprocess.run(
            ["node", "-e", f"new Function({json.dumps(js_code)})"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, (
            f"JS syntax error in gg-ab-tests.js: {result.stderr.strip()}"
        )

    def test_bootstrap_snippet_syntax(self):
        from brand_tokens import get_ab_head_snippet
        snippet = get_ab_head_snippet()
        # Extract JS from <script>...</script>
        import re
        match = re.search(r"<script>(.*?)</script>", snippet)
        assert match, "No inline script found in AB head snippet"
        js_code = match.group(1)
        result = subprocess.run(
            ["node", "-e", f"new Function({json.dumps(js_code)})"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, (
            f"JS syntax error in AB bootstrap: {result.stderr.strip()}"
        )


# ── Generator Integration ────────────────────────────────────


class TestGeneratorDataAbAttrs:
    """Verify that generators produce data-ab attributes matching experiment selectors."""

    @pytest.fixture(scope="class")
    def experiment_selectors(self):
        """Extract data-ab values from experiment selectors."""
        import re
        selectors = {}
        for exp in EXPERIMENTS:
            match = re.search(r"data-ab=['\"]([^'\"]+)['\"]", exp["selector"])
            if match:
                selectors[exp["id"]] = match.group(1)
        return selectors

    def test_all_selectors_use_data_ab(self, experiment_selectors):
        assert len(experiment_selectors) == len(EXPERIMENTS), (
            "Not all experiments use data-ab selectors"
        )

    def test_homepage_has_data_ab_attrs(self, experiment_selectors):
        hp_file = PROJECT_ROOT / "wordpress" / "generate_homepage.py"
        content = hp_file.read_text()
        homepage_experiments = [
            e for e in EXPERIMENTS if "/" in e["pages"] or "/index.html" in e["pages"]
        ]
        for exp in homepage_experiments:
            ab_val = experiment_selectors.get(exp["id"])
            if ab_val:
                assert f'data-ab="{ab_val}"' in content, (
                    f"Homepage missing data-ab=\"{ab_val}\" for {exp['id']}"
                )

    def test_about_has_data_ab_attrs(self, experiment_selectors):
        about_file = PROJECT_ROOT / "wordpress" / "generate_about.py"
        content = about_file.read_text()
        about_experiments = [
            e for e in EXPERIMENTS if "/about/" in e["pages"]
        ]
        for exp in about_experiments:
            ab_val = experiment_selectors.get(exp["id"])
            if ab_val:
                assert f'data-ab="{ab_val}"' in content, (
                    f"About page missing data-ab=\"{ab_val}\" for {exp['id']}"
                )

    def test_homepage_has_ab_head_snippet(self):
        hp_file = PROJECT_ROOT / "wordpress" / "generate_homepage.py"
        content = hp_file.read_text()
        assert "get_ab_head_snippet()" in content, (
            "Homepage missing get_ab_head_snippet() call"
        )

    def test_about_has_ab_head_snippet(self):
        about_file = PROJECT_ROOT / "wordpress" / "generate_about.py"
        content = about_file.read_text()
        assert "get_ab_head_snippet()" in content, (
            "About page missing get_ab_head_snippet() call"
        )


# ── Config File Sync ─────────────────────────────────────────


class TestConfigSync:
    def test_experiments_json_exists_or_can_be_generated(self):
        config_path = PROJECT_ROOT / "web" / "ab" / "experiments.json"
        if config_path.exists():
            data = json.loads(config_path.read_text())
            assert "version" in data
            assert "experiments" in data
        else:
            # File doesn't exist yet — that's OK before first export
            pytest.skip("experiments.json not yet generated")

    def test_experiments_json_matches_source(self):
        config_path = PROJECT_ROOT / "web" / "ab" / "experiments.json"
        if not config_path.exists():
            pytest.skip("experiments.json not yet generated")
        on_disk = json.loads(config_path.read_text())
        from_source = export_config()
        assert on_disk["experiments"] == from_source["experiments"], (
            "experiments.json is stale — run: python wordpress/ab_experiments.py"
        )


# ── MU-Plugin ────────────────────────────────────────────────


class TestMuPlugin:
    def test_gg_ab_php_exists(self):
        php_file = PROJECT_ROOT / "wordpress" / "mu-plugins" / "gg-ab.php"
        assert php_file.exists(), f"Missing: {php_file}"

    def test_gg_ab_php_has_correct_priority(self):
        php_file = PROJECT_ROOT / "wordpress" / "mu-plugins" / "gg-ab.php"
        content = php_file.read_text()
        assert "gg_ab_bootstrap" in content
        assert "'wp_head'" in content
        assert ", 2 )" in content, "AB mu-plugin should have priority 2 (after GA4's 1)"

    def test_gg_ab_php_skips_admin(self):
        php_file = PROJECT_ROOT / "wordpress" / "mu-plugins" / "gg-ab.php"
        content = php_file.read_text()
        assert "is_admin()" in content
        assert "edit_posts" in content
