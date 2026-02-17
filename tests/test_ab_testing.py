"""Tests for A/B testing system — config, JS runtime behavior, report stats,
generator integration, bootstrap parity, and deploy pipeline.

Target: 80+ test methods covering every surface that can silently break.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))

from ab_experiments import EXPERIMENTS, export_config, validate_experiments


# ── Helpers ──────────────────────────────────────────────────


def run_js(code: str, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run JS code via Node.js and return result."""
    return subprocess.run(
        ["node", "-e", code],
        capture_output=True, text=True, timeout=timeout,
    )


def get_ab_js() -> str:
    """Read the main gg-ab-tests.js file."""
    return (PROJECT_ROOT / "web" / "gg-ab-tests.js").read_text()


# Load JS functions into Node for runtime testing.
# Strip the IIFE wrapper and fetch() call so we can test individual functions.
def _extract_js_functions() -> str:
    """Extract inner functions from the IIFE for unit testing in Node."""
    js = get_ab_js()
    # Remove the IIFE wrapper: (function () { ... })();
    inner = re.search(r"\(function\s*\(\)\s*\{(.*)\}\)\(\);", js, re.DOTALL)
    if not inner:
        raise ValueError("Could not extract IIFE inner content from gg-ab-tests.js")
    body = inner.group(1)
    # Remove the fetch() call at the bottom (it would fail in Node)
    body = re.sub(r"fetch\(CONFIG_URL\).*$", "", body, flags=re.DOTALL)
    # Remove 'use strict' (already in function scope)
    body = body.replace("'use strict';", "")
    return body


JS_FUNCTIONS = _extract_js_functions()


# ── 1. Config Validation (10 tests) ─────────────────────────


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

    def test_no_duplicate_selectors(self):
        """Two experiments must not target the same data-ab selector."""
        selectors = [e["selector"] for e in EXPERIMENTS]
        assert len(selectors) == len(set(selectors)), (
            f"Duplicate selectors: {[s for s in selectors if selectors.count(s) > 1]}"
        )

    def test_dates_use_date_objects_properly(self):
        """Start/end dates must be valid ISO format and comparable."""
        from datetime import date as dt_date
        for exp in EXPERIMENTS:
            if exp.get("start"):
                parsed = dt_date.fromisoformat(exp["start"])
                assert isinstance(parsed, dt_date)
            if exp.get("end"):
                parsed = dt_date.fromisoformat(exp["end"])
                assert isinstance(parsed, dt_date)
            if exp.get("start") and exp.get("end"):
                assert exp["start"] <= exp["end"], (
                    f"{exp['id']}: start {exp['start']} > end {exp['end']}"
                )


# ── 2. Export / JSON (5 tests) ───────────────────────────────


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

    def test_export_includes_conversion(self):
        """Every exported experiment must have conversion config for tracking."""
        config = export_config()
        for exp in config["experiments"]:
            assert "conversion" in exp, f"{exp['id']}: missing conversion in export"
            assert exp["conversion"].get("selector"), (
                f"{exp['id']}: conversion missing selector in export"
            )


# ── 3. JS Syntax (3 tests) ──────────────────────────────────


class TestJsSyntax:
    def test_ab_tests_js_syntax(self):
        js_file = PROJECT_ROOT / "web" / "gg-ab-tests.js"
        assert js_file.exists(), f"Missing: {js_file}"
        js_code = js_file.read_text()
        result = run_js(f"new Function({json.dumps(js_code)})")
        assert result.returncode == 0, (
            f"JS syntax error in gg-ab-tests.js: {result.stderr.strip()}"
        )

    def test_bootstrap_snippet_syntax(self):
        from brand_tokens import get_ab_bootstrap_js
        js_code = get_ab_bootstrap_js()
        result = run_js(f"new Function({json.dumps(js_code)})")
        assert result.returncode == 0, (
            f"JS syntax error in AB bootstrap: {result.stderr.strip()}"
        )

    def test_extracted_functions_parse(self):
        """The extracted JS functions used for runtime testing must parse."""
        result = run_js(f"new Function({json.dumps(JS_FUNCTIONS)})")
        assert result.returncode == 0, (
            f"Extracted JS functions don't parse: {result.stderr.strip()}"
        )


# ── 4. FNV-1a Hash Runtime (6 tests) ────────────────────────


class TestFnv1aHash:
    """Verify FNV-1a hash is deterministic and distributed."""

    def _run_fnv(self, input_str: str) -> int:
        code = f"""
{JS_FUNCTIONS}
console.log(fnv1a({json.dumps(input_str)}));
"""
        result = run_js(code)
        assert result.returncode == 0, f"fnv1a failed: {result.stderr}"
        return int(result.stdout.strip())

    def test_deterministic_same_input(self):
        h1 = self._run_fnv("visitor123:experiment_1")
        h2 = self._run_fnv("visitor123:experiment_1")
        assert h1 == h2, "FNV-1a not deterministic"

    def test_different_inputs_different_hashes(self):
        h1 = self._run_fnv("visitor_a:exp_1")
        h2 = self._run_fnv("visitor_b:exp_1")
        assert h1 != h2, "Different inputs produced same hash"

    def test_different_experiments_different_hashes(self):
        h1 = self._run_fnv("same_visitor:exp_1")
        h2 = self._run_fnv("same_visitor:exp_2")
        assert h1 != h2, "Same visitor, different experiments should get different hashes"

    def test_returns_unsigned_32bit(self):
        h = self._run_fnv("test_string")
        assert 0 <= h <= 0xFFFFFFFF, f"Hash {h} out of 32-bit unsigned range"

    def test_empty_string(self):
        h = self._run_fnv("")
        assert isinstance(h, int)
        assert h > 0

    def test_known_value(self):
        """FNV-1a of empty string should be the offset basis."""
        h = self._run_fnv("")
        # FNV-1a offset basis is 2166136261 (0x811c9dc5)
        assert h == 2166136261, f"FNV-1a('') = {h}, expected 2166136261"


# ── 5. Variant Assignment Runtime (8 tests) ─────────────────


class TestVariantAssignment:
    """Verify deterministic variant assignment via Node.js."""

    def _assign(self, visitor_id: str, experiment: dict) -> str | None:
        code = f"""
{JS_FUNCTIONS}
var result = assignVariant({json.dumps(visitor_id)}, {json.dumps(experiment)});
console.log(result ? result.id : 'null');
"""
        result = run_js(code)
        assert result.returncode == 0, f"assignVariant failed: {result.stderr}"
        val = result.stdout.strip()
        return None if val == "null" else val

    MOCK_EXP = {
        "id": "test_exp",
        "traffic": 1.0,
        "variants": [
            {"id": "control", "name": "Control", "content": "A"},
            {"id": "variant_a", "name": "Variant A", "content": "B"},
            {"id": "variant_b", "name": "Variant B", "content": "C"},
        ],
    }

    def test_returns_valid_variant_id(self):
        result = self._assign("visitor_1", self.MOCK_EXP)
        assert result in ("control", "variant_a", "variant_b"), f"Got: {result}"

    def test_deterministic_same_visitor(self):
        r1 = self._assign("visitor_stable", self.MOCK_EXP)
        r2 = self._assign("visitor_stable", self.MOCK_EXP)
        assert r1 == r2, "Same visitor got different assignments"

    def test_different_visitors_get_distributed(self):
        """100 visitors should produce at least 2 different variants."""
        seen = set()
        code_lines = [JS_FUNCTIONS]
        for i in range(100):
            code_lines.append(
                f'console.log(assignVariant("v{i}", {json.dumps(self.MOCK_EXP)}).id);'
            )
        result = run_js("\n".join(code_lines))
        assert result.returncode == 0, f"Failed: {result.stderr}"
        for line in result.stdout.strip().split("\n"):
            seen.add(line.strip())
        assert len(seen) >= 2, f"100 visitors only saw {seen} — no distribution"

    def test_traffic_zero_point_five_excludes_some(self):
        exp = {**self.MOCK_EXP, "traffic": 0.5}
        assigned = 0
        code_lines = [JS_FUNCTIONS]
        for i in range(200):
            code_lines.append(
                f'var r = assignVariant("visitor_{i}", {json.dumps(exp)}); '
                f'console.log(r ? "1" : "0");'
            )
        result = run_js("\n".join(code_lines))
        assert result.returncode == 0
        for line in result.stdout.strip().split("\n"):
            assigned += int(line.strip())
        # With traffic=0.5, expect roughly 50% ± 15%
        assert 70 <= assigned <= 130, (
            f"traffic=0.5 assigned {assigned}/200 (expected ~100)"
        )

    def test_traffic_one_includes_all(self):
        assigned = 0
        code_lines = [JS_FUNCTIONS]
        for i in range(50):
            code_lines.append(
                f'var r = assignVariant("v_{i}", {json.dumps(self.MOCK_EXP)}); '
                f'console.log(r ? "1" : "0");'
            )
        result = run_js("\n".join(code_lines))
        assert result.returncode == 0
        for line in result.stdout.strip().split("\n"):
            assigned += int(line.strip())
        assert assigned == 50, f"traffic=1.0 should include all, got {assigned}/50"

    def test_two_variant_experiment(self):
        """Works with exactly 2 variants (minimum)."""
        exp = {
            "id": "two_var",
            "traffic": 1.0,
            "variants": [
                {"id": "control", "name": "C", "content": "X"},
                {"id": "variant_a", "name": "A", "content": "Y"},
            ],
        }
        result = self._assign("test_visitor", exp)
        assert result in ("control", "variant_a")

    def test_assignment_stable_across_experiments(self):
        """Same visitor, different experiment IDs — independent assignments."""
        exp_a = {**self.MOCK_EXP, "id": "exp_alpha"}
        exp_b = {**self.MOCK_EXP, "id": "exp_beta"}
        r_a = self._assign("shared_visitor", exp_a)
        r_b = self._assign("shared_visitor", exp_b)
        # They CAN be the same by chance, but the assignment is independent
        assert r_a is not None and r_b is not None

    def test_variant_index_never_out_of_bounds(self):
        """hash % variants.length must always be in range."""
        code_lines = [JS_FUNCTIONS]
        for i in range(500):
            code_lines.append(
                f'var r = assignVariant("v{i}", {json.dumps(self.MOCK_EXP)}); '
                f'if (!r) {{ console.log("ERROR_NULL"); process.exit(1); }}'
            )
        code_lines.append('console.log("OK");')
        result = run_js("\n".join(code_lines))
        assert result.returncode == 0, f"Out-of-bounds variant: {result.stdout}"


# ── 6. Page Matching Runtime (7 tests) ───────────────────────


class TestPageMatching:
    """Verify matchesPage() handles URL edge cases."""

    def _matches(self, pages: list, pathname: str) -> bool:
        code = f"""
{JS_FUNCTIONS}
// Mock location.pathname
global.location = {{ pathname: {json.dumps(pathname)} }};
console.log(matchesPage({json.dumps(pages)}) ? 'true' : 'false');
"""
        result = run_js(code)
        assert result.returncode == 0, f"matchesPage failed: {result.stderr}"
        return result.stdout.strip() == "true"

    def test_exact_match(self):
        assert self._matches(["/about/"], "/about/")

    def test_root_matches_index_html(self):
        assert self._matches(["/"], "/index.html")

    def test_index_html_matches_root(self):
        assert self._matches(["/index.html"], "/")

    def test_trailing_slash_normalization(self):
        assert self._matches(["/about"], "/about/")

    def test_no_match(self):
        assert not self._matches(["/about/"], "/coaching/")

    def test_multiple_pages(self):
        assert self._matches(["/about/", "/coaching/"], "/coaching/")

    def test_empty_pages_no_match(self):
        assert not self._matches([], "/")


# ── 7. ab_report.py Statistical Tests (10 tests) ────────────


class TestChiSquared:
    """Test the statistical analysis in ab_report.py."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from ab_report import chi_squared_test, analyze
        self.chi_sq = chi_squared_test
        self.analyze = analyze

    def test_identical_rates_not_significant(self):
        """Same conversion rate in both groups → high p-value."""
        p = self.chi_sq(1000, 100, 1000, 100)
        assert p > 0.05, f"Identical rates should not be significant: p={p}"

    def test_very_different_rates_significant(self):
        """Wildly different rates → low p-value."""
        p = self.chi_sq(1000, 50, 1000, 200)
        if p == 1.0:
            pytest.skip("scipy not installed — chi-squared returns fallback p=1.0")
        assert p < 0.05, f"Very different rates should be significant: p={p}"

    def test_zero_control_impressions(self):
        p = self.chi_sq(0, 0, 100, 10)
        assert p == 1.0

    def test_zero_variant_impressions(self):
        p = self.chi_sq(100, 10, 0, 0)
        assert p == 1.0

    def test_negative_conversions_returns_one(self):
        p = self.chi_sq(100, -5, 100, 10)
        assert p == 1.0

    def test_p_value_between_zero_and_one(self):
        p = self.chi_sq(500, 50, 500, 75)
        assert 0 <= p <= 1.0, f"p-value out of range: {p}"

    def test_analyze_mock_data(self):
        """Run full analysis pipeline with mock data."""
        mock = {
            "impressions": {
                "test_exp": {"control": 500, "variant_a": 500},
            },
            "conversions": {
                "test_exp": {"control": 50, "variant_a": 75},
            },
        }
        reports = self.analyze(mock)
        assert len(reports) >= 1
        r = reports[0]
        assert r["experiment_id"] == "test_exp"
        assert r["total_impressions"] == 1000
        assert len(r["variants"]) == 2

    def test_analyze_declares_winner_when_significant(self):
        """Large sample + big lift → winner declared."""
        mock = {
            "impressions": {
                "test_exp": {"control": 2000, "variant_a": 2000},
            },
            "conversions": {
                "test_exp": {"control": 100, "variant_a": 300},
            },
        }
        reports = self.analyze(mock)
        r = reports[0]
        try:
            import scipy  # noqa: F401
        except ImportError:
            pytest.skip("scipy not installed — cannot test winner declaration")
        assert r["status"] == "winner", f"Expected winner, got: {r['status']}"
        assert r["winner"] == "variant_a"

    def test_analyze_no_winner_when_insufficient_data(self):
        """Below MIN_SAMPLE_SIZE → collecting status."""
        mock = {
            "impressions": {
                "test_exp": {"control": 10, "variant_a": 10},
            },
            "conversions": {
                "test_exp": {"control": 1, "variant_a": 5},
            },
        }
        reports = self.analyze(mock)
        r = reports[0]
        assert r["status"] == "collecting"
        assert r["winner"] is None

    def test_analyze_lift_calculation(self):
        """Verify lift = (variant_rate - control_rate) / control_rate."""
        mock = {
            "impressions": {
                "test_exp": {"control": 1000, "variant_a": 1000},
            },
            "conversions": {
                "test_exp": {"control": 100, "variant_a": 150},
            },
        }
        reports = self.analyze(mock)
        variant_a = [v for v in reports[0]["variants"] if v["variant_id"] == "variant_a"][0]
        expected_lift = (0.15 - 0.10) / 0.10  # 0.5 = 50% lift
        assert abs(variant_a["lift"] - expected_lift) < 0.01, (
            f"Lift {variant_a['lift']} != expected {expected_lift}"
        )


# ── 8. Selector-Generator Parity (7 tests) ──────────────────


class TestSelectorGeneratorParity:
    """Cross-reference experiment selectors against generator output.

    This catches the case where someone changes a data-ab value in a generator
    but forgets to update the experiment config (or vice versa).
    """

    @pytest.fixture(scope="class")
    def experiment_ab_values(self):
        """Extract data-ab values from experiment selectors."""
        values = {}
        for exp in EXPERIMENTS:
            match = re.search(r"data-ab=['\"]([^'\"]+)['\"]", exp["selector"])
            if match:
                values[exp["id"]] = match.group(1)
        return values

    @pytest.fixture(scope="class")
    def homepage_content(self):
        return (PROJECT_ROOT / "wordpress" / "generate_homepage.py").read_text()

    @pytest.fixture(scope="class")
    def about_content(self):
        return (PROJECT_ROOT / "wordpress" / "generate_about.py").read_text()

    def test_all_selectors_use_data_ab(self, experiment_ab_values):
        assert len(experiment_ab_values) == len(EXPERIMENTS), (
            "Not all experiments use data-ab selectors"
        )

    def test_homepage_has_all_required_data_ab_attrs(self, experiment_ab_values, homepage_content):
        homepage_experiments = [
            e for e in EXPERIMENTS if "/" in e["pages"] or "/index.html" in e["pages"]
        ]
        for exp in homepage_experiments:
            ab_val = experiment_ab_values.get(exp["id"])
            if ab_val:
                assert f'data-ab="{ab_val}"' in homepage_content, (
                    f"Homepage missing data-ab=\"{ab_val}\" for {exp['id']}"
                )

    def test_about_has_all_required_data_ab_attrs(self, experiment_ab_values, about_content):
        about_experiments = [
            e for e in EXPERIMENTS if "/about/" in e["pages"]
        ]
        for exp in about_experiments:
            ab_val = experiment_ab_values.get(exp["id"])
            if ab_val:
                assert f'data-ab="{ab_val}"' in about_content, (
                    f"About page missing data-ab=\"{ab_val}\" for {exp['id']}"
                )

    def test_homepage_has_ab_head_snippet(self, homepage_content):
        assert "get_ab_head_snippet()" in homepage_content, (
            "Homepage missing get_ab_head_snippet() call"
        )

    def test_about_has_ab_head_snippet(self, about_content):
        assert "get_ab_head_snippet()" in about_content, (
            "About page missing get_ab_head_snippet() call"
        )

    def test_no_orphaned_data_ab_in_homepage(self, experiment_ab_values, homepage_content):
        """Every data-ab in the generator must have a corresponding experiment."""
        known_values = set(experiment_ab_values.values())
        for match in re.finditer(r'data-ab="([^"]+)"', homepage_content):
            val = match.group(1)
            assert val in known_values, (
                f"Homepage has data-ab=\"{val}\" but no experiment uses it"
            )

    def test_no_orphaned_data_ab_in_about(self, experiment_ab_values, about_content):
        """Every data-ab in the about generator must have a corresponding experiment."""
        known_values = set(experiment_ab_values.values())
        for match in re.finditer(r'data-ab="([^"]+)"', about_content):
            val = match.group(1)
            assert val in known_values, (
                f"About page has data-ab=\"{val}\" but no experiment uses it"
            )


# ── 9. Bootstrap Parity (4 tests) ───────────────────────────


class TestBootstrapParity:
    """Ensure the inline bootstrap JS is identical in brand_tokens.py and gg-ab.php."""

    def test_bootstrap_js_parity(self):
        """The minified bootstrap in PHP must match Python's get_ab_bootstrap_js()."""
        from brand_tokens import get_ab_bootstrap_js
        python_bootstrap = get_ab_bootstrap_js()

        php_file = PROJECT_ROOT / "wordpress" / "mu-plugins" / "gg-ab.php"
        php_content = php_file.read_text()
        # Extract JS from the echo statement
        match = re.search(r"echo '(\(function\(\)\{.*?\}\)\(\);)'", php_content)
        assert match, "Could not find bootstrap JS in gg-ab.php"
        php_bootstrap = match.group(1)

        assert python_bootstrap == php_bootstrap, (
            "Bootstrap JS mismatch between brand_tokens.py and gg-ab.php!\n"
            f"  Python: {python_bootstrap[:80]}...\n"
            f"  PHP:    {php_bootstrap[:80]}..."
        )

    def test_bootstrap_is_valid_js(self):
        from brand_tokens import get_ab_bootstrap_js
        js = get_ab_bootstrap_js()
        result = run_js(f"new Function({json.dumps(js)})")
        assert result.returncode == 0

    def test_head_snippet_contains_defer(self):
        from brand_tokens import get_ab_head_snippet
        snippet = get_ab_head_snippet()
        assert "defer" in snippet, "AB script tag should be deferred"

    def test_head_snippet_contains_hashed_filename(self):
        """Static page snippet should use cache-busted filename."""
        from brand_tokens import get_ab_head_snippet, get_ab_js_filename
        snippet = get_ab_head_snippet()
        expected = get_ab_js_filename()
        assert expected in snippet, (
            f"Head snippet should reference {expected}, got: {snippet}"
        )


# ── 10. Config File Sync (3 tests) ──────────────────────────


class TestConfigSync:
    def test_experiments_json_exists(self):
        config_path = PROJECT_ROOT / "web" / "ab" / "experiments.json"
        assert config_path.exists(), (
            "experiments.json missing — run: python wordpress/ab_experiments.py"
        )

    def test_experiments_json_valid_structure(self):
        config_path = PROJECT_ROOT / "web" / "ab" / "experiments.json"
        if not config_path.exists():
            pytest.skip("experiments.json not yet generated")
        data = json.loads(config_path.read_text())
        assert "version" in data
        assert "experiments" in data
        assert isinstance(data["experiments"], list)

    def test_experiments_json_matches_source(self):
        config_path = PROJECT_ROOT / "web" / "ab" / "experiments.json"
        if not config_path.exists():
            pytest.skip("experiments.json not yet generated")
        on_disk = json.loads(config_path.read_text())
        from_source = export_config()
        assert on_disk["experiments"] == from_source["experiments"], (
            "experiments.json is stale — run: python wordpress/ab_experiments.py"
        )


# ── 11. MU-Plugin (4 tests) ─────────────────────────────────


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

    def test_gg_ab_php_has_parity_note(self):
        """PHP file must document the parity requirement with brand_tokens.py."""
        php_file = PROJECT_ROOT / "wordpress" / "mu-plugins" / "gg-ab.php"
        content = php_file.read_text()
        assert "brand_tokens.py" in content, (
            "gg-ab.php must reference brand_tokens.py parity requirement"
        )


# ── 12. Cache Busting (3 tests) ─────────────────────────────


class TestCacheBusting:
    def test_js_filename_contains_hash(self):
        from brand_tokens import get_ab_js_filename
        name = get_ab_js_filename()
        assert re.match(r"gg-ab-tests\.[a-f0-9]{8}\.js$", name), (
            f"Expected hashed filename, got: {name}"
        )

    def test_hash_changes_with_content(self):
        """Different JS content should produce different hashes."""
        import hashlib
        js_path = PROJECT_ROOT / "web" / "gg-ab-tests.js"
        content = js_path.read_text()
        h1 = hashlib.md5(content.encode()).hexdigest()[:8]
        h2 = hashlib.md5((content + "// change").encode()).hexdigest()[:8]
        assert h1 != h2, "Hash should change when content changes"

    def test_hash_stable_for_same_content(self):
        from brand_tokens import get_ab_js_filename
        n1 = get_ab_js_filename()
        n2 = get_ab_js_filename()
        assert n1 == n2, "Same content should produce same hash"


# ── 13. Conversion Deduplication (2 tests) ───────────────────


class TestConversionDedup:
    def test_js_uses_session_storage_dedup(self):
        """Conversion handler must use sessionStorage to deduplicate."""
        js = get_ab_js()
        assert "sessionStorage" in js, (
            "Conversion tracking must use sessionStorage for dedup"
        )

    def test_dedup_key_includes_experiment_id(self):
        """Dedup key must be per-experiment, not global."""
        js = get_ab_js()
        assert "gg_ab_conv_" in js, (
            "Dedup key should be prefixed with gg_ab_conv_ + experiment.id"
        )


# ── 14. File Existence (3 tests) ────────────────────────────


class TestFileExistence:
    """All AB system files must exist."""

    def test_js_file_exists(self):
        assert (PROJECT_ROOT / "web" / "gg-ab-tests.js").exists()

    def test_config_dir_exists(self):
        assert (PROJECT_ROOT / "web" / "ab").is_dir()

    def test_mu_plugin_exists(self):
        assert (PROJECT_ROOT / "wordpress" / "mu-plugins" / "gg-ab.php").exists()


# ── 15. JS applyVariant Correctness (3 tests) ───────────────


class TestApplyVariantCorrectness:
    """Verify applyVariant uses textContent (not innerHTML) for safety."""

    def test_uses_textcontent(self):
        """applyVariant must use textContent for XSS safety."""
        js = get_ab_js()
        apply_fn = re.search(r"function applyVariant.*?\n  \}", js, re.DOTALL)
        assert apply_fn, "Could not find applyVariant function"
        body = apply_fn.group(0)
        assert "textContent" in body
        # Check code lines only (strip comments)
        code_lines = [
            line for line in body.split("\n")
            if line.strip() and not line.strip().startswith("//")
        ]
        code_only = "\n".join(code_lines)
        assert "innerHTML" not in code_only, (
            "applyVariant must NOT use innerHTML in code — all variants are plain text"
        )

    def test_no_dead_code_branches(self):
        """applyVariant should not have if/else branches that do the same thing."""
        js = get_ab_js()
        apply_fn = re.search(r"function applyVariant.*?\n  \}", js, re.DOTALL)
        assert apply_fn, "Could not find applyVariant function"
        body = apply_fn.group(0)
        # Count textContent assignments — should be exactly 1
        assignments = re.findall(r"\.textContent\s*=", body)
        assert len(assignments) == 1, (
            f"applyVariant has {len(assignments)} textContent assignments, expected 1 "
            "(dead code if >1)"
        )
