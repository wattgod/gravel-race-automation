"""Tests for meta description generation, validation, and mu-plugin structure."""

import json
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSON_FILE = PROJECT_ROOT / "seo" / "meta-descriptions.json"
MU_PLUGIN = PROJECT_ROOT / "wordpress" / "mu-plugins" / "gg-meta-descriptions.php"
GENERATOR = PROJECT_ROOT / "scripts" / "generate_meta_descriptions.py"
RACE_DATA_DIR = PROJECT_ROOT / "race-data"


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def meta_data():
    """Load meta-descriptions.json."""
    assert JSON_FILE.exists(), f"Missing {JSON_FILE} — run generate_meta_descriptions.py"
    return json.loads(JSON_FILE.read_text())


@pytest.fixture(scope="module")
def entries(meta_data):
    """Return entries list from meta-descriptions.json."""
    return meta_data["entries"]


# ── JSON Structure Tests ──────────────────────────────────────────────

class TestJsonStructure:
    def test_has_entries_key(self, meta_data):
        assert "entries" in meta_data

    def test_entry_count(self, entries):
        assert len(entries) == 131, f"Expected 131 entries, got {len(entries)}"

    def test_page_count(self, entries):
        pages = [e for e in entries if e["wp_type"] == "page"]
        assert len(pages) == 54, f"Expected 54 pages, got {len(pages)}"

    def test_post_count(self, entries):
        posts = [e for e in entries if e["wp_type"] == "post"]
        assert len(posts) == 77, f"Expected 77 posts, got {len(posts)}"

    def test_required_fields(self, entries):
        required = {"wp_id", "wp_type", "slug", "description"}
        for e in entries:
            missing = required - set(e.keys())
            assert not missing, f"wp_id={e.get('wp_id')}: missing {missing}"

    def test_valid_wp_type(self, entries):
        for e in entries:
            assert e["wp_type"] in ("page", "post"), \
                f"wp_id={e['wp_id']}: invalid wp_type '{e['wp_type']}'"

    def test_wp_ids_are_integers(self, entries):
        for e in entries:
            assert isinstance(e["wp_id"], int), \
                f"wp_id should be int, got {type(e['wp_id'])}"

    def test_sorted_by_wp_id(self, entries):
        ids = [e["wp_id"] for e in entries]
        assert ids == sorted(ids), "Entries should be sorted by wp_id"


# ── Description Quality Tests ─────────────────────────────────────────

class TestDescriptionQuality:
    def test_min_length(self, entries):
        for e in entries:
            assert len(e["description"]) >= 50, \
                f"wp_id={e['wp_id']}: too short ({len(e['description'])} chars)"

    def test_max_length(self, entries):
        for e in entries:
            assert len(e["description"]) <= 160, \
                f"wp_id={e['wp_id']}: too long ({len(e['description'])} chars)"

    def test_no_duplicate_descriptions(self, entries):
        descs = [e["description"] for e in entries]
        seen = {}
        for e in entries:
            desc = e["description"]
            assert desc not in seen, \
                f"Duplicate: wp_id={e['wp_id']} and wp_id={seen[desc]}"
            seen[desc] = e["wp_id"]

    def test_no_repr_leaks(self, entries):
        """Ensure no Python repr() artifacts in descriptions."""
        for e in entries:
            for field in ("description",):
                val = e.get(field, "")
                assert "\\n" not in val, f"wp_id={e['wp_id']}: escaped newline in {field}"
                assert "\\t" not in val, f"wp_id={e['wp_id']}: escaped tab in {field}"
                assert not val.startswith("["), f"wp_id={e['wp_id']}: starts with [ in {field}"
                assert not val.startswith("{"), f"wp_id={e['wp_id']}: starts with {{ in {field}"
                assert "\\'" not in val, f"wp_id={e['wp_id']}: escaped quote in {field}"

    def test_no_html_in_descriptions(self, entries):
        """Descriptions should be plain text, no HTML tags."""
        html_pattern = re.compile(r"<[a-zA-Z/]")
        for e in entries:
            assert not html_pattern.search(e["description"]), \
                f"wp_id={e['wp_id']}: HTML found in description"

    def test_descriptions_end_with_punctuation(self, entries):
        """All descriptions should end with proper punctuation."""
        for e in entries:
            assert e["description"].rstrip()[-1] in ".?!", \
                f"wp_id={e['wp_id']}: description doesn't end with punctuation"

    def test_og_description_length(self, entries):
        """OG descriptions, when present, should be <= 160 chars."""
        for e in entries:
            og = e.get("og_description")
            if og:
                assert len(og) <= 160, \
                    f"wp_id={e['wp_id']}: og_description too long ({len(og)})"


# ── Title Quality Tests ──────────────────────────────────────────────

class TestTitleQuality:
    def test_all_entries_have_titles(self, entries):
        for e in entries:
            assert e.get("title"), \
                f"wp_id={e['wp_id']}: missing title"

    def test_title_min_length(self, entries):
        for e in entries:
            title = e.get("title", "")
            if title:
                assert len(title) >= 30, \
                    f"wp_id={e['wp_id']}: title too short ({len(title)} chars)"

    def test_title_max_length(self, entries):
        for e in entries:
            title = e.get("title", "")
            if title:
                assert len(title) <= 60, \
                    f"wp_id={e['wp_id']}: title too long ({len(title)} chars)"

    def test_title_ends_with_brand(self, entries):
        for e in entries:
            title = e.get("title", "")
            if title:
                assert title.endswith("| Gravel God"), \
                    f"wp_id={e['wp_id']}: title must end with '| Gravel God'"

    def test_no_duplicate_titles(self, entries):
        seen = {}
        for e in entries:
            title = e.get("title")
            if title:
                assert title not in seen, \
                    f"Duplicate title: wp_id={e['wp_id']} and wp_id={seen[title]}"
                seen[title] = e["wp_id"]

    def test_title_no_html(self, entries):
        html_pattern = re.compile(r"<[a-zA-Z/]")
        for e in entries:
            title = e.get("title", "")
            if title:
                assert not html_pattern.search(title), \
                    f"wp_id={e['wp_id']}: HTML found in title"


# ── WP ID Coverage Tests ─────────────────────────────────────────────

class TestCoverage:
    SKIP_IDS = {3938, 3246, 3245, 3244}

    def test_unique_wp_ids(self, entries):
        ids = [e["wp_id"] for e in entries]
        assert len(ids) == len(set(ids)), f"Duplicate wp_ids found"

    def test_no_skipped_ids(self, entries):
        """Skipped utility pages should not be in the data."""
        entry_ids = {e["wp_id"] for e in entries}
        for skip_id in self.SKIP_IDS:
            assert skip_id not in entry_ids, \
                f"Skipped page wp_id={skip_id} should not be in entries"

    def test_core_pages_present(self, entries):
        """Key pages must have entries."""
        entry_ids = {e["wp_id"] for e in entries}
        core_ids = {
            448: "home",
            5018: "gravel-races",
            5016: "training-plans",
            5043: "coaching",
            5045: "articles",
        }
        for wp_id, name in core_ids.items():
            assert wp_id in entry_ids, f"Core page '{name}' (wp_id={wp_id}) missing"


# ── Race Guide Template Tests ────────────────────────────────────────

class TestRaceGuideTemplates:
    def test_race_guide_entries_have_source(self, entries):
        """Race guide entries should be tagged with source=race-data."""
        race_guide = [e for e in entries if e.get("source") == "race-data"]
        assert len(race_guide) >= 20, \
            f"Expected >=20 race-data entries, got {len(race_guide)}"

    def test_race_guide_entries_have_race_slug(self, entries):
        """Race guide entries should reference their race-data slug."""
        for e in entries:
            if e.get("source") == "race-data":
                assert "race_data_slug" in e, \
                    f"wp_id={e['wp_id']}: race-data entry missing race_data_slug"

    def test_race_guide_slugs_exist(self, entries):
        """All referenced race-data slugs should have matching JSON files."""
        for e in entries:
            slug = e.get("race_data_slug")
            if slug:
                json_path = RACE_DATA_DIR / f"{slug}.json"
                assert json_path.exists(), \
                    f"wp_id={e['wp_id']}: race-data/{slug}.json not found"

    def test_race_guide_descriptions_contain_tier(self, entries):
        """Race guide descriptions should mention the tier."""
        for e in entries:
            if e.get("source") == "race-data":
                assert "Tier " in e["description"], \
                    f"wp_id={e['wp_id']}: missing Tier in description"

    def test_race_guide_descriptions_contain_score(self, entries):
        """Race guide descriptions should mention the score."""
        for e in entries:
            if e.get("source") == "race-data":
                assert "/100" in e["description"], \
                    f"wp_id={e['wp_id']}: missing score in description"

    def test_race_guide_count(self, entries):
        """All 22 race guide pages must have entries."""
        race_guide = [e for e in entries if e.get("source") == "race-data"]
        assert len(race_guide) == 22, f"Expected 22 race-data entries, got {len(race_guide)}"

    def test_race_guide_focus_keywords(self, entries):
        """All race guide entries should have focus keywords that appear in their description."""
        for e in entries:
            if e.get("source") == "race-data":
                kw = e.get("focus_keyword")
                assert kw, f"wp_id={e['wp_id']}: missing focus_keyword"
                assert kw.lower() in e["description"].lower(), \
                    f"wp_id={e['wp_id']}: focus_keyword '{kw}' not in description"


# ── mu-plugin Tests ──────────────────────────────────────────────────

class TestMuPlugin:
    def test_mu_plugin_exists(self):
        assert MU_PLUGIN.exists(), f"Missing {MU_PLUGIN}"

    def test_mu_plugin_has_header(self):
        content = MU_PLUGIN.read_text()
        assert "Plugin Name:" in content

    def test_mu_plugin_has_abspath_guard(self):
        content = MU_PLUGIN.read_text()
        assert "ABSPATH" in content

    def test_mu_plugin_hooks_aioseo_title(self):
        content = MU_PLUGIN.read_text()
        assert "aioseo_title" in content

    def test_mu_plugin_hooks_aioseo_description(self):
        content = MU_PLUGIN.read_text()
        assert "aioseo_description" in content

    def test_mu_plugin_hooks_aioseo_og_description(self):
        content = MU_PLUGIN.read_text()
        assert "aioseo_og_description" in content

    def test_mu_plugin_has_title_filter(self):
        """mu-plugin must have gg_meta_filter_title function."""
        content = MU_PLUGIN.read_text()
        assert "gg_meta_filter_title" in content

    def test_mu_plugin_reads_json(self):
        content = MU_PLUGIN.read_text()
        assert "gg-meta-descriptions.json" in content

    def test_mu_plugin_uses_static_cache(self):
        content = MU_PLUGIN.read_text()
        assert "static $data" in content

    def test_mu_plugin_indexes_by_wp_id(self):
        content = MU_PLUGIN.read_text()
        assert "wp_id" in content

    def test_mu_plugin_has_deploy_command(self):
        content = MU_PLUGIN.read_text()
        assert "--sync-meta-descriptions" in content

    def test_mu_plugin_has_singular_guard(self):
        """mu-plugin must check is_singular() to avoid overriding archive descriptions."""
        content = MU_PLUGIN.read_text()
        assert "is_singular()" in content, \
            "Missing is_singular() guard — get_the_ID() returns wrong ID on archives"

    def test_mu_plugin_uses_get_queried_object_id(self):
        """mu-plugin should use get_queried_object_id() for reliable post ID outside loop."""
        content = MU_PLUGIN.read_text()
        assert "get_queried_object_id()" in content, \
            "Should use get_queried_object_id() — more reliable than get_the_ID() outside loop"

    def test_mu_plugin_has_post_id_helper(self):
        """mu-plugin should have a centralized post ID helper to avoid duplicated logic."""
        content = MU_PLUGIN.read_text()
        assert "gg_meta_get_post_id" in content, \
            "Should have gg_meta_get_post_id() helper to centralize post ID logic"


# ── Standalone Race Page Tests ──────────────────────────────────────

class TestStandaloneRacePages:
    """Standalone race pages must have unique descriptions, not template filler."""

    STANDALONE_SLUGS = {
        "barry-roubaix", "sbt-grvl", "belgian-waffle-ride",
        "mid-south", "unbound-200", "unbound-200-2", "crusher-in-the-tushar",
    }

    def test_standalone_pages_are_manual(self, entries):
        """Standalone race pages should be manual entries, not template-generated."""
        for e in entries:
            if e["slug"] in self.STANDALONE_SLUGS:
                assert e.get("source") == "manual", \
                    f"wp_id={e['wp_id']} ({e['slug']}): standalone race page should be " \
                    f"manual entry, not source={e.get('source')}"

    def test_standalone_pages_not_generic(self, entries):
        """Standalone pages must not use generic filler phrases."""
        filler_phrases = [
            "Training plans, race strategy, and course intel",
            "Training plans and race strategy",
        ]
        for e in entries:
            if e["slug"] in self.STANDALONE_SLUGS:
                for filler in filler_phrases:
                    assert filler not in e["description"], \
                        f"wp_id={e['wp_id']} ({e['slug']}): uses generic filler '{filler}'"

    def test_standalone_vs_guide_descriptions_differ(self, entries):
        """Standalone race page descriptions must differ from their race-guide counterparts."""
        # Map standalone slugs to their guide slugs
        guide_map = {
            "barry-roubaix": "barry-roubaix-race-guide",
            "sbt-grvl": "sbt-grvl-race-guide",
            "belgian-waffle-ride": "belgian-waffle-ride-race-guide",
            "mid-south": "mid-south-race-guide",
            "unbound-200": "unbound-200-race-guide",
            "crusher-in-the-tushar": "crusher-tushar-race-guide",
        }
        descs_by_slug = {e["slug"]: e["description"] for e in entries}
        for standalone, guide in guide_map.items():
            if standalone in descs_by_slug and guide in descs_by_slug:
                assert descs_by_slug[standalone] != descs_by_slug[guide], \
                    f"Standalone '{standalone}' has same description as guide '{guide}'"


# ── Generator Script Tests ───────────────────────────────────────────

class TestGeneratorScript:
    def test_generator_exists(self):
        assert GENERATOR.exists(), f"Missing {GENERATOR}"

    def test_generator_has_race_guide_entries(self):
        content = GENERATOR.read_text()
        assert "RACE_GUIDE_ENTRIES" in content

    def test_generator_has_manual_entries(self):
        content = GENERATOR.read_text()
        assert "MANUAL_ENTRIES" in content

    def test_generator_has_all_expected_flags(self):
        content = GENERATOR.read_text()
        assert "--dry-run" in content
        assert "--stats" in content
        assert "--validate" in content

    def test_generator_is_idempotent(self):
        """Running the generator twice must produce identical output."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("gen", str(GENERATOR))
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        run1 = gen.generate_entries()
        run2 = gen.generate_entries()
        assert len(run1) == len(run2), "Entry count differs between runs"
        for a, b in zip(run1, run2):
            assert a == b, f"Mismatch for wp_id={a.get('wp_id')}"


# ── Deploy Function Tests ────────────────────────────────────────────

class TestDeployFunction:
    """Tests for sync_meta_descriptions() in push_wordpress.py."""

    PUSH_SCRIPT = PROJECT_ROOT / "scripts" / "push_wordpress.py"

    def test_push_script_has_sync_flag(self):
        content = self.PUSH_SCRIPT.read_text()
        assert "--sync-meta-descriptions" in content

    def test_push_script_has_sync_function(self):
        content = self.PUSH_SCRIPT.read_text()
        assert "def sync_meta_descriptions" in content

    def test_push_script_validates_json_count(self):
        """Deploy must validate entry count before uploading."""
        content = self.PUSH_SCRIPT.read_text()
        assert "< 100" in content or ">= 100" in content, \
            "sync_meta_descriptions should validate entry count"

    def test_push_script_uploads_both_files(self):
        """Deploy must upload both the mu-plugin and JSON data."""
        content = self.PUSH_SCRIPT.read_text()
        assert "gg-meta-descriptions.php" in content
        assert "gg-meta-descriptions.json" in content

    def test_push_script_included_in_deploy_all(self):
        """--sync-meta-descriptions should be included in --deploy-all."""
        content = self.PUSH_SCRIPT.read_text()
        assert "sync_meta_descriptions = True" in content, \
            "--sync-meta-descriptions not included in --deploy-all"

    def test_push_script_uploads_json_before_php(self):
        """JSON data must be uploaded before the mu-plugin to avoid race condition."""
        content = self.PUSH_SCRIPT.read_text()
        json_pos = content.find("gg-meta-descriptions.json")
        php_pos = content.find("gg-meta-descriptions.php", content.find("def sync_meta_descriptions"))
        # Skip the variable definition lines — find the actual SCP upload lines
        json_scp = content.find("gg-meta-descriptions.json", content.find("scp", content.find("def sync_meta_descriptions")))
        php_scp = content.find("gg-meta-descriptions.php", content.find("scp", content.find("def sync_meta_descriptions")))
        assert json_scp < php_scp, \
            "JSON data must be uploaded before PHP mu-plugin"

    def test_push_script_sets_permissions(self):
        """Deploy should set file permissions after SCP."""
        content = self.PUSH_SCRIPT.read_text()
        assert "chmod 644" in content, \
            "Should chmod 644 deployed files"


# ── Validate Deploy Tests ────────────────────────────────────────────

class TestValidateDeploy:
    """Tests for check_meta_descriptions() in validate_deploy.py."""

    VALIDATE_SCRIPT = PROJECT_ROOT / "scripts" / "validate_deploy.py"

    def test_validate_has_check_function(self):
        content = self.VALIDATE_SCRIPT.read_text()
        assert "def check_meta_descriptions" in content

    def test_validate_uses_html_escape(self):
        """Deploy validation must HTML-escape descriptions before matching."""
        content = self.VALIDATE_SCRIPT.read_text()
        assert "html.escape" in content or "html_mod.escape" in content, \
            "Must HTML-escape descriptions — raw string match breaks on & < > chars"

    def test_validate_registered_in_main(self):
        content = self.VALIDATE_SCRIPT.read_text()
        assert "check_meta_descriptions(v)" in content


# ── Preflight Tests ─────────────────────────────────────────────────

class TestPreflight:
    """Tests for meta description checks in preflight_quality.py."""

    PREFLIGHT_SCRIPT = PROJECT_ROOT / "scripts" / "preflight_quality.py"

    def test_preflight_has_focus_keyword_check(self):
        """Preflight must validate focus keywords appear in descriptions."""
        content = self.PREFLIGHT_SCRIPT.read_text()
        assert "focus_keyword" in content, \
            "preflight_quality.py should check focus keywords"

    def test_preflight_has_php_syntax_check(self):
        """Preflight must validate PHP syntax of mu-plugin files."""
        content = self.PREFLIGHT_SCRIPT.read_text()
        assert "check_mu_plugin_php_syntax" in content, \
            "preflight_quality.py should have PHP syntax validation"

    def test_preflight_php_check_registered_in_main(self):
        """PHP syntax check must be called from main."""
        content = self.PREFLIGHT_SCRIPT.read_text()
        assert "check_mu_plugin_php_syntax()" in content, \
            "check_mu_plugin_php_syntax() not called from main"
