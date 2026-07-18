"""Tests for AI-search ingestibility: markdown mirrors, IndexNow, llms freshness.

Covers:
  - the static IndexNow key file matches the constant in scripts/indexnow_ping.py
  - web/llms.txt states the markdown mirror URL pattern
  - scripts/generate_markdown_profiles.py produces output for a real slug
  - scripts/indexnow_ping.py's payload builder (no network)

The alternate-link `<link rel="alternate" type="text/markdown">` tag in the
race page head is covered separately in
tests/test_neo_brutalist.py::TestFullPage::test_has_markdown_alternate_link.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# conftest.py already puts scripts/ on sys.path
import indexnow_ping
import generate_markdown_profiles

LLMS_TXT = PROJECT_ROOT / "web" / "llms.txt"


# ── IndexNow key file ──────────────────────────────────────────────────

class TestIndexNowKeyFile:
    def test_key_file_exists(self):
        key_file = PROJECT_ROOT / "web" / f"{indexnow_ping.INDEXNOW_KEY}.txt"
        assert key_file.exists(), f"Missing {key_file} — expected to hold the IndexNow key"

    def test_key_file_content_matches_constant(self):
        key_file = PROJECT_ROOT / "web" / f"{indexnow_ping.INDEXNOW_KEY}.txt"
        if not key_file.exists():
            pytest.skip(f"{key_file} not present")
        assert key_file.read_text().strip() == indexnow_ping.INDEXNOW_KEY

    def test_key_is_64_hex_chars(self):
        key = indexnow_ping.INDEXNOW_KEY
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


# ── llms.txt freshness/markdown pattern ─────────────────────────────────

class TestLlmsTxtMarkdownPattern:
    def test_llms_txt_mentions_markdown_url_pattern(self):
        if not LLMS_TXT.exists():
            pytest.skip("web/llms.txt not generated — run generate_llms_txt.py first")
        content = LLMS_TXT.read_text()
        assert "gravelgodcycling.com/race/{slug}.md" in content
        assert "Markdown Mirrors" in content


# ── Markdown profile generator ──────────────────────────────────────────

class TestMarkdownGenerator:
    def test_generator_produces_output_for_a_sample_slug(self):
        """generate_profile() must produce non-empty markdown with YAML
        frontmatter for at least one real race in the index. Scans a bounded
        prefix rather than requiring a hardcoded slug, since not every race's
        source data is guaranteed to be well-formed."""
        if not generate_markdown_profiles.INDEX_FILE.exists():
            pytest.skip("web/race-index.json not present")

        index = json.loads(generate_markdown_profiles.INDEX_FILE.read_text())
        index_map = {r["slug"]: r for r in index}

        produced = None
        for entry in index[:30]:
            slug = entry["slug"]
            try:
                md = generate_markdown_profiles.generate_profile(
                    slug, index_map[slug], generate_markdown_profiles.RACE_DATA_DIR
                )
            except Exception:
                continue
            if md:
                produced = (slug, md)
                break

        assert produced is not None, "No race in the first 30 index entries produced markdown output"
        slug, md = produced
        assert md.startswith("---"), "Markdown profile must open with YAML frontmatter"
        assert f'slug: "{slug}"' in md
        assert f"https://gravelgodcycling.com/race/{slug}/" in md


# ── IndexNow payload builder (no network) ───────────────────────────────

class TestIndexNowPayloadBuilder:
    def test_build_payload_shape(self):
        urls = ["https://gravelgodcycling.com/race/a.md", "https://gravelgodcycling.com/race/b.md"]
        payload = indexnow_ping.build_payload(urls)
        assert payload["host"] == "gravelgodcycling.com"
        assert payload["key"] == indexnow_ping.INDEXNOW_KEY
        assert payload["keyLocation"] == f"https://gravelgodcycling.com/{indexnow_ping.INDEXNOW_KEY}.txt"
        assert payload["urlList"] == urls

    def test_build_payload_accepts_overrides(self):
        payload = indexnow_ping.build_payload(["https://example.com/x"], host="example.com", key="deadbeef")
        assert payload["host"] == "example.com"
        assert payload["key"] == "deadbeef"
        assert payload["keyLocation"] == "https://gravelgodcycling.com/deadbeef.txt"

    def test_urls_from_index_uses_race_urls(self):
        if not (PROJECT_ROOT / "web" / "race-index.json").exists():
            pytest.skip("web/race-index.json not present")
        urls = indexnow_ping.urls_from_index()
        assert urls
        assert all(u.startswith("https://gravelgodcycling.com/race/") and u.endswith("/") for u in urls)

    def test_dry_run_ping_makes_no_network_call(self):
        codes = indexnow_ping.ping(["https://gravelgodcycling.com/race/a.md"], dry_run=True)
        assert codes == [None]
