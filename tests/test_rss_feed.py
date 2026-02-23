"""Tests for the RSS feed generator."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FEED_FILE = PROJECT_ROOT / "web" / "feed" / "races.xml"
GENERATOR = PROJECT_ROOT / "scripts" / "generate_rss_feed.py"
PUSH_SCRIPT = PROJECT_ROOT / "scripts" / "push_wordpress.py"
HOMEPAGE_GEN = PROJECT_ROOT / "wordpress" / "generate_homepage.py"
HEADER_PLUGIN = PROJECT_ROOT / "wordpress" / "mu-plugins" / "gg-header.php"
ROBOTS_TXT = PROJECT_ROOT / "web" / "robots.txt"


class TestFeedFile:
    """Tests for the generated RSS feed."""

    def test_file_exists(self):
        assert FEED_FILE.exists(), "races.xml not found"

    def test_valid_xml(self):
        ET.parse(str(FEED_FILE))

    def test_is_rss2(self):
        tree = ET.parse(str(FEED_FILE))
        root = tree.getroot()
        assert root.tag == "rss"
        assert root.attrib.get("version") == "2.0"

    def test_has_channel(self):
        tree = ET.parse(str(FEED_FILE))
        root = tree.getroot()
        channel = root.find("channel")
        assert channel is not None

    def test_channel_title(self):
        tree = ET.parse(str(FEED_FILE))
        channel = tree.getroot().find("channel")
        title = channel.find("title")
        assert title is not None
        assert "Gravel God" in title.text

    def test_channel_link(self):
        tree = ET.parse(str(FEED_FILE))
        channel = tree.getroot().find("channel")
        link = channel.find("link")
        assert link is not None
        assert "gravelgodcycling.com" in link.text

    def test_channel_description(self):
        tree = ET.parse(str(FEED_FILE))
        channel = tree.getroot().find("channel")
        desc = channel.find("description")
        assert desc is not None
        assert "328" in desc.text
        assert "14 criteria" in desc.text

    def test_has_atom_self_link(self):
        content = FEED_FILE.read_text()
        assert "atom:link" in content
        assert 'rel="self"' in content
        assert "races.xml" in content

    def test_has_328_items(self):
        tree = ET.parse(str(FEED_FILE))
        channel = tree.getroot().find("channel")
        items = channel.findall("item")
        assert len(items) == 328, f"Expected 328 items, got {len(items)}"

    def test_items_have_required_fields(self):
        tree = ET.parse(str(FEED_FILE))
        channel = tree.getroot().find("channel")
        items = channel.findall("item")
        for item in items[:10]:
            assert item.find("title") is not None
            assert item.find("link") is not None
            assert item.find("guid") is not None
            assert item.find("description") is not None
            assert item.find("pubDate") is not None

    def test_items_link_to_race_profiles(self):
        tree = ET.parse(str(FEED_FILE))
        channel = tree.getroot().find("channel")
        items = channel.findall("item")
        for item in items[:10]:
            link = item.find("link").text
            assert link.startswith("https://gravelgodcycling.com/race/")
            assert link.endswith("/")

    def test_items_have_categories(self):
        tree = ET.parse(str(FEED_FILE))
        channel = tree.getroot().find("channel")
        items = channel.findall("item")
        for item in items[:10]:
            cats = item.findall("category")
            assert len(cats) >= 1, "Each item should have at least a tier category"

    def test_tier_categories_present(self):
        content = FEED_FILE.read_text()
        for tier in (1, 2, 3, 4):
            assert f"<category>Tier {tier}</category>" in content

    def test_titles_include_tier_and_score(self):
        tree = ET.parse(str(FEED_FILE))
        channel = tree.getroot().find("channel")
        items = channel.findall("item")
        for item in items[:5]:
            title = item.find("title").text
            assert "Tier" in title
            assert "/100" in title

    def test_t1_races_appear_first(self):
        tree = ET.parse(str(FEED_FILE))
        channel = tree.getroot().find("channel")
        items = channel.findall("item")
        first_title = items[0].find("title").text
        assert "Tier 1" in first_title

    def test_guid_is_permalink(self):
        tree = ET.parse(str(FEED_FILE))
        channel = tree.getroot().find("channel")
        items = channel.findall("item")
        for item in items[:5]:
            guid = item.find("guid")
            assert guid.attrib.get("isPermaLink") == "true"

    def test_file_size_reasonable(self):
        size = FEED_FILE.stat().st_size
        # 328 items should be ~100-300KB
        assert 50_000 < size < 500_000, f"Unexpected feed size: {size:,} bytes"


class TestGenerator:
    """Tests for generate_rss_feed.py."""

    def test_generator_exists(self):
        assert GENERATOR.exists()

    def test_generator_has_dry_run(self):
        content = GENERATOR.read_text()
        assert "--dry-run" in content

    def test_generator_uses_14_criteria(self):
        content = GENERATOR.read_text()
        assert "14 criteria" in content


class TestIntegration:
    """Tests for RSS feed integration with other components."""

    def test_homepage_has_rss_link(self):
        content = HOMEPAGE_GEN.read_text()
        assert "application/rss+xml" in content
        assert "races.xml" in content

    def test_header_plugin_has_rss_link(self):
        content = HEADER_PLUGIN.read_text()
        assert "application/rss+xml" in content
        assert "races.xml" in content

    def test_robots_mentions_feed(self):
        content = ROBOTS_TXT.read_text()
        assert "races.xml" in content


class TestDeployFunction:
    """Tests for sync_rss in push_wordpress.py."""

    def test_sync_flag_exists(self):
        content = PUSH_SCRIPT.read_text()
        assert "--sync-rss" in content

    def test_sync_function_exists(self):
        content = PUSH_SCRIPT.read_text()
        assert "def sync_rss" in content

    def test_included_in_deploy_all(self):
        content = PUSH_SCRIPT.read_text()
        assert "args.sync_rss = True" in content

    def test_dispatched_in_main(self):
        content = PUSH_SCRIPT.read_text()
        assert "if args.sync_rss:" in content
        assert "sync_rss()" in content
