"""Tests for the embeddable race badge widget."""

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EMBED_DIR = PROJECT_ROOT / "web" / "embed"
EMBED_DATA = EMBED_DIR / "embed-data.json"
EMBED_JS = EMBED_DIR / "gg-embed.js"
EMBED_DEMO = EMBED_DIR / "demo.html"
GENERATOR = PROJECT_ROOT / "scripts" / "generate_embed_widget.py"
PUSH_SCRIPT = PROJECT_ROOT / "scripts" / "push_wordpress.py"


class TestEmbedData:
    """Tests for embed-data.json."""

    def test_file_exists(self):
        assert EMBED_DATA.exists(), "embed-data.json not found"

    def test_valid_json(self):
        data = json.loads(EMBED_DATA.read_text())
        assert isinstance(data, list)

    def test_has_all_races(self):
        data = json.loads(EMBED_DATA.read_text())
        assert len(data) == 328, f"Expected 328 races, got {len(data)}"

    def test_entry_has_required_fields(self):
        data = json.loads(EMBED_DATA.read_text())
        required = {"s", "n", "t", "sc", "l", "u"}
        for entry in data[:10]:  # Check first 10
            missing = required - set(entry.keys())
            assert not missing, f"Missing fields {missing} in {entry.get('s', '?')}"

    def test_slug_field(self):
        data = json.loads(EMBED_DATA.read_text())
        slugs = [e["s"] for e in data]
        assert "unbound-200" in slugs
        assert "leadville-100" in slugs

    def test_tier_range(self):
        data = json.loads(EMBED_DATA.read_text())
        for entry in data:
            assert entry["t"] in (1, 2, 3, 4), f"Invalid tier {entry['t']} for {entry['s']}"

    def test_score_range(self):
        data = json.loads(EMBED_DATA.read_text())
        for entry in data:
            assert 0 <= entry["sc"] <= 100, f"Invalid score {entry['sc']} for {entry['s']}"

    def test_url_format(self):
        data = json.loads(EMBED_DATA.read_text())
        for entry in data:
            assert entry["u"].startswith("https://gravelgodcycling.com/race/")
            assert entry["u"].endswith("/")

    def test_unique_slugs(self):
        data = json.loads(EMBED_DATA.read_text())
        slugs = [e["s"] for e in data]
        assert len(slugs) == len(set(slugs)), "Duplicate slugs in embed data"

    def test_compact_format(self):
        """Embed data uses short keys for minimal payload."""
        data = json.loads(EMBED_DATA.read_text())
        entry = data[0]
        # Short keys: s=slug, n=name, t=tier, sc=score, l=location, d=date, u=url
        assert "slug" not in entry, "Use short keys (s, not slug)"
        assert "name" not in entry, "Use short keys (n, not name)"
        assert "tier" not in entry, "Use short keys (t, not tier)"

    def test_file_size_reasonable(self):
        size = EMBED_DATA.stat().st_size
        assert size < 100_000, f"Embed data too large: {size:,} bytes (max 100KB)"


class TestEmbedJS:
    """Tests for gg-embed.js."""

    def test_file_exists(self):
        assert EMBED_JS.exists(), "gg-embed.js not found"

    def test_is_iife(self):
        content = EMBED_JS.read_text()
        assert content.strip().startswith("(function()"), "JS should be an IIFE"
        assert content.strip().endswith("})();"), "JS should end IIFE"

    def test_contains_data_url(self):
        content = EMBED_JS.read_text()
        assert "embed-data.json" in content

    def test_contains_site_url(self):
        content = EMBED_JS.read_text()
        assert "gravelgodcycling.com" in content

    def test_contains_css(self):
        content = EMBED_JS.read_text()
        assert ".gg-embed-card" in content
        assert ".gg-embed-tier" in content

    def test_contains_ga4_event(self):
        content = EMBED_JS.read_text()
        assert "embed_load" in content

    def test_handles_unknown_slug(self):
        content = EMBED_JS.read_text()
        assert "Race not found" in content

    def test_escapes_html(self):
        content = EMBED_JS.read_text()
        assert "esc(" in content or "textContent" in content

    def test_tier_css_classes(self):
        content = EMBED_JS.read_text()
        for tier in (1, 2, 3, 4):
            assert f"gg-embed-tier-{tier}" in content

    def test_no_border_radius(self):
        """Neo-brutalist brand rule: no border-radius."""
        content = EMBED_JS.read_text()
        assert "border-radius:0" in content or "border-radius" not in content

    def test_file_size_reasonable(self):
        size = EMBED_JS.stat().st_size
        assert size < 10_000, f"Embed JS too large: {size:,} bytes (max 10KB)"


class TestEmbedDemo:
    """Tests for demo.html."""

    def test_file_exists(self):
        assert EMBED_DEMO.exists(), "demo.html not found"

    def test_has_example_embeds(self):
        content = EMBED_DEMO.read_text()
        assert 'data-slug="unbound-200"' in content
        assert 'data-slug="leadville-100"' in content

    def test_has_copy_paste_code(self):
        content = EMBED_DEMO.read_text()
        assert "gg-embed.js" in content
        assert 'class="gg-embed"' in content

    def test_references_local_js(self):
        content = EMBED_DEMO.read_text()
        assert 'src="gg-embed.js"' in content


class TestGenerator:
    """Tests for generate_embed_widget.py."""

    def test_generator_exists(self):
        assert GENERATOR.exists()

    def test_generator_has_dry_run(self):
        content = GENERATOR.read_text()
        assert "--dry-run" in content


class TestDeployFunction:
    """Tests for sync_embed in push_wordpress.py."""

    def test_sync_flag_exists(self):
        content = PUSH_SCRIPT.read_text()
        assert "--sync-embed" in content

    def test_sync_function_exists(self):
        content = PUSH_SCRIPT.read_text()
        assert "def sync_embed" in content

    def test_included_in_deploy_all(self):
        content = PUSH_SCRIPT.read_text()
        assert "args.sync_embed = True" in content

    def test_dispatched_in_main(self):
        content = PUSH_SCRIPT.read_text()
        assert "if args.sync_embed:" in content
        assert "sync_embed()" in content
