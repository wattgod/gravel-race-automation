"""Phase 2 catalog-contract tests for the Matti-approved road migration."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))

from scripts import generate_index
from scripts import generate_markdown_profiles
from scripts import push_wordpress
from scripts import road_migration
from wordpress.generate_neo_brutalist import generate_page, load_race_data


MAP_PATH = PROJECT_ROOT / "docs" / "specs" / "road-migration-map.json"
INDEX_PATH = PROJECT_ROOT / "web" / "race-index.json"
DELETION_PATH = (
    PROJECT_ROOT / "docs" / "specs" / "road-migration-server-deletions.txt"
)
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
ROAD_ARCHIVE_DIR = PROJECT_ROOT / "race-data-archived" / "road"
QUARANTINE_DIR = (
    PROJECT_ROOT / "race-data-archived" / "quarantined-fabrications"
)


@pytest.fixture(scope="module")
def migration_map():
    return road_migration.load_approved_map(MAP_PATH)


@pytest.fixture(scope="module")
def race_index():
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


class TestApprovedDisposition:
    def test_map_action_counts(self, migration_map):
        counts = Counter(entry["action"] for entry in migration_map["entries"])
        assert counts == Counter(
            redirect=358,
            hub_redirect=5,
            keep_on_gg=1,
        )

    def test_archive_file_counts_and_locations(self):
        assert len(list(ROAD_ARCHIVE_DIR.glob("*.json"))) == 359
        assert len(list(QUARANTINE_DIR.glob("*.json"))) == 4
        assert {
            path.stem for path in QUARANTINE_DIR.glob("*.json")
        } == road_migration.QUARANTINED_FABRICATIONS

    def test_all_map_profiles_have_one_disposition_location(self, migration_map):
        active = {path.stem for path in RACE_DATA_DIR.glob("*.json")}
        road_archive = {path.stem for path in ROAD_ARCHIVE_DIR.glob("*.json")}
        quarantine = {path.stem for path in QUARANTINE_DIR.glob("*.json")}
        for entry in migration_map["entries"]:
            slug = entry["gg"]["slug"]
            locations = sum(
                slug in slugs
                for slugs in (active, road_archive, quarantine)
            )
            assert locations == 1, f"{slug} has {locations} data locations"


class TestCatalogContract:
    def test_road_count_is_zero(self, race_index):
        assert sum(race.get("discipline") == "road" for race in race_index) == 0

    def test_post_migration_catalog_count_has_map_provenance(
        self, migration_map, race_index
    ):
        # Phase 1 source snapshot: 733 active profiles. Phase 2 removes the
        # 363 redirect/hub_redirect records and keeps RVO, yielding 370.
        source_count = migration_map["source_snapshot"]["gravel_god"][
            "race_data_total_profiles"
        ]
        departing_count = len(road_migration.redirected_entries(migration_map))
        assert len(race_index) == source_count - departing_count == 370

    def test_archived_profiles_never_feed_generated_index(
        self, migration_map, race_index
    ):
        index_slugs = {race["slug"] for race in race_index}
        archived_slugs = {
            entry["gg"]["slug"]
            for entry in road_migration.redirected_entries(migration_map)
        }
        assert index_slugs.isdisjoint(archived_slugs)

    def test_profile_loader_is_non_recursive_and_excludes_archive(self, tmp_path):
        active_dir = tmp_path / "race-data"
        archive_dir = tmp_path / "race-data-archived" / "road"
        active_dir.mkdir()
        archive_dir.mkdir(parents=True)
        (active_dir / "active-race.json").write_text(
            '{"race":{"slug":"active-race"}}',
            encoding="utf-8",
        )
        (archive_dir / "archived-road.json").write_text(
            '{"race":{"slug":"archived-road"}}',
            encoding="utf-8",
        )

        assert set(generate_index.load_profiles(active_dir)) == {"active-race"}

    def test_rift_valley_odyssey_is_present_as_mtb(self, race_index):
        by_slug = {race["slug"]: race for race in race_index}
        assert by_slug["rift-valley-odyssey"]["discipline"] == "mtb"

        profile = json.loads(
            (RACE_DATA_DIR / "rift-valley-odyssey.json").read_text(
                encoding="utf-8"
            )
        )["race"]
        assert profile["vitals"]["discipline"] == "mtb"
        assert profile["gravel_god_rating"]["discipline"] == "mtb"

    def test_rift_valley_odyssey_renders_as_mtb(self):
        rd = load_race_data(RACE_DATA_DIR / "rift-valley-odyssey.json")
        page = generate_page(rd)
        assert '<span class="gg-series-badge">MTB</span>' in page
        assert '"sport":"Mountain Biking"' in page


class TestDeletionList:
    def test_deletion_list_matches_map_exactly(self, migration_map):
        expected = road_migration.generate_server_deletion_paths(migration_map)
        actual = DELETION_PATH.read_text(encoding="utf-8").splitlines()
        assert actual == expected

    def test_deletion_list_is_explicit_and_rvo_absent(self):
        paths = DELETION_PATH.read_text(encoding="utf-8").splitlines()
        # 364 map entries minus the one keep-on-GG RVO disposition.
        assert len(paths) == 726
        assert sum(path.endswith("/") for path in paths) == 363
        assert sum(path.endswith(".md") for path in paths) == 363
        assert not any("*" in path or "?" in path for path in paths)
        assert not any("rift-valley-odyssey" in path for path in paths)


class TestRedirectGeneration:
    def test_pair_and_rule_counts(self, migration_map):
        rules = road_migration.generate_redirect_rules(
            migration_map, RACE_DATA_DIR
        )
        assert len(rules) == 726
        assert sum(road_migration.ROADIE_LABS_HUB in rule for rule in rules) == 10
        assert sum(
            "https://roadielabs.com/race/" in rule for rule in rules
        ) == 716

    def test_no_remaining_catalog_collision(self, migration_map):
        road_migration.assert_no_remaining_slug_collisions(
            migration_map, RACE_DATA_DIR
        )

    def test_collision_guard_fails_closed(self, migration_map, tmp_path):
        colliding = tmp_path / "race-data"
        colliding.mkdir()
        (colliding / "mallorca-312.json").write_text(
            '{"race":{"slug":"mallorca-312"}}',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="collide"):
            road_migration.generate_redirect_rules(migration_map, colliding)

    def test_rvo_absent_and_fabrications_use_hub(self, migration_map):
        rules = road_migration.generate_redirect_rules(
            migration_map, RACE_DATA_DIR
        )
        rendered = "\n".join(rules)
        assert "rift-valley-odyssey" not in rendered
        for slug in road_migration.QUARANTINED_FABRICATIONS:
            matches = [
                rule for rule in rules if f"race/{slug}" in rule
            ]
            assert len(matches) == 2
            assert all(road_migration.ROADIE_LABS_HUB in rule for rule in matches)

    def test_managed_redirect_block_contains_one_generated_section(self):
        block = push_wordpress.REDIRECT_BLOCK
        assert block.count(road_migration.REDIRECT_SECTION_BEGIN) == 1
        assert block.count(road_migration.REDIRECT_SECTION_END) == 1
        assert len(push_wordpress.ROAD_MIGRATION_REDIRECT_RULES) == 726


class TestRegeneratedCopies:
    def test_sitemap_has_no_departed_race_scoped_urls(self, migration_map):
        sitemap = (PROJECT_ROOT / "web" / "sitemap.xml").read_text(
            encoding="utf-8"
        )
        for entry in road_migration.redirected_entries(migration_map):
            slug = entry["gg"]["slug"]
            assert f"/race/{slug}/" not in sitemap

    def test_search_directory_matches_active_index(self, migration_map, race_index):
        widget = (
            PROJECT_ROOT / "web" / "gravel-race-search.html"
        ).read_text(encoding="utf-8")
        directory_slugs = set(
            re.findall(
                r'<a href="/race/([^"/]+)/" class="gg-directory-link">',
                widget,
            )
        )
        assert directory_slugs == {race["slug"] for race in race_index}
        assert not any(
            entry["gg"]["slug"] in directory_slugs
            for entry in road_migration.redirected_entries(migration_map)
        )

    def test_embed_copy_matches_active_index(self, race_index):
        embed = json.loads(
            (PROJECT_ROOT / "web" / "embed" / "embed-data.json").read_text(
                encoding="utf-8"
            )
        )
        assert {entry["s"] for entry in embed} == {
            race["slug"] for race in race_index
        }

    def test_jsonld_copy_matches_active_profiles(self, race_index):
        generated = {
            path.stem for path in (PROJECT_ROOT / "web" / "jsonld").glob("*.jsonld")
        }
        expected = {
            race["slug"] for race in race_index if race.get("has_profile")
        }
        assert generated == expected

    def test_full_markdown_generation_prunes_stale_files(
        self, race_index, tmp_path, monkeypatch
    ):
        source_profile = RACE_DATA_DIR / "unbound-200.json"
        data_dir = tmp_path / "race-data"
        data_dir.mkdir()
        (data_dir / source_profile.name).write_text(
            source_profile.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        index_path = tmp_path / "race-index.json"
        index_path.write_text(
            json.dumps(
                [next(race for race in race_index if race["slug"] == "unbound-200")]
            ),
            encoding="utf-8",
        )
        output_dir = tmp_path / "markdown"
        output_dir.mkdir()
        (output_dir / "departed-road.md").write_text("stale", encoding="utf-8")

        monkeypatch.setattr(generate_markdown_profiles, "INDEX_FILE", index_path)
        monkeypatch.setattr(generate_markdown_profiles, "RACE_DATA_DIR", data_dir)
        monkeypatch.setattr(
            "scripts.training_plan_inventory.fetch_live_training_plan_slugs",
            lambda: set(),
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "generate_markdown_profiles.py",
                "--output-dir",
                str(output_dir),
            ],
        )

        assert generate_markdown_profiles.main() == 0
        assert {path.name for path in output_dir.glob("*.md")} == {
            "unbound-200.md"
        }
