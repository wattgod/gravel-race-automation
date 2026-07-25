#!/usr/bin/env python3
"""Generate the local artifacts for the approved road-catalog migration.

This module is intentionally build-only. It reads the owner-approved migration
map, renders explicit server deletion paths and Apache redirect rules, and
refuses to generate redirects that collide with the remaining GG catalog.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAP_PATH = PROJECT_ROOT / "docs" / "specs" / "road-migration-map.json"
DEFAULT_DELETION_PATH = (
    PROJECT_ROOT / "docs" / "specs" / "road-migration-server-deletions.txt"
)
DEFAULT_RACE_DATA_DIR = PROJECT_ROOT / "race-data"
ROADIE_LABS_HUB = "https://roadielabs.com/road-races/"

EXPECTED_TOTAL = 364
EXPECTED_ACTION_COUNTS = {
    "redirect": 358,
    "hub_redirect": 5,
    "keep_on_gg": 1,
}
QUARANTINED_FABRICATIONS = frozenset(
    {
        "chase-the-sun-norway",
        "fuji-panorama-gran-fondo",
        "gran-fondo-sibiu",
        "vietnam-cycling-challenge",
    }
)
KEEP_ON_GG_SLUG = "rift-valley-odyssey"

REDIRECT_SECTION_BEGIN = "# BEGIN GENERATED ROAD MIGRATION REDIRECTS"
REDIRECT_SECTION_END = "# END GENERATED ROAD MIGRATION REDIRECTS"

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PAGE_PATH_RE = re.compile(r"^/race/[a-z0-9]+(?:-[a-z0-9]+)*/$")
_MARKDOWN_PATH_RE = re.compile(r"^/race/[a-z0-9]+(?:-[a-z0-9]+)*\.md$")


def load_approved_map(map_path: Path = DEFAULT_MAP_PATH) -> dict:
    """Load and validate the Matti-approved Phase 1 migration map."""
    migration_map = json.loads(Path(map_path).read_text(encoding="utf-8"))
    entries = migration_map.get("entries", [])
    approval = migration_map.get("approval", {})

    if approval.get("approved_by") != "Matti" or approval.get("approved_on") != "2026-07-24":
        raise ValueError("road migration map is not the Matti-approved 2026-07-24 map")
    if len(entries) != EXPECTED_TOTAL:
        raise ValueError(f"expected {EXPECTED_TOTAL} map entries, found {len(entries)}")

    slugs = [entry.get("gg", {}).get("slug") for entry in entries]
    if len(set(slugs)) != EXPECTED_TOTAL or any(
        not isinstance(slug, str) or not _SLUG_RE.fullmatch(slug)
        for slug in slugs
    ):
        raise ValueError("map GG slugs must be 364 unique canonical slugs")

    action_counts = Counter(entry.get("action") for entry in entries)
    if dict(action_counts) != EXPECTED_ACTION_COUNTS:
        raise ValueError(
            f"unexpected map action counts: {dict(action_counts)} "
            f"(expected {EXPECTED_ACTION_COUNTS})"
        )

    by_slug = {entry["gg"]["slug"]: entry for entry in entries}
    if by_slug[KEEP_ON_GG_SLUG].get("action") != "keep_on_gg":
        raise ValueError("Rift Valley Odyssey must remain keep_on_gg")
    if any(by_slug[slug].get("action") != "hub_redirect"
           for slug in QUARANTINED_FABRICATIONS):
        raise ValueError("all four quarantined fabrications must use hub_redirect")

    return migration_map


def redirected_entries(migration_map: dict) -> list[dict]:
    """Return the 363 GG entries that leave the catalog, sorted by source slug."""
    return sorted(
        (
            entry
            for entry in migration_map["entries"]
            if entry.get("action") in {"redirect", "hub_redirect"}
        ),
        key=lambda entry: entry["gg"]["slug"],
    )


def remaining_catalog_slugs(
    race_data_dir: Path = DEFAULT_RACE_DATA_DIR,
) -> set[str]:
    """Return canonical slugs from the active, non-archived data directory."""
    return {path.stem for path in Path(race_data_dir).glob("*.json")}


def assert_no_remaining_slug_collisions(
    migration_map: dict,
    race_data_dir: Path = DEFAULT_RACE_DATA_DIR,
) -> None:
    """Refuse redirect generation if a source slug is still an active GG race."""
    redirect_slugs = {
        entry["gg"]["slug"] for entry in redirected_entries(migration_map)
    }
    collisions = sorted(redirect_slugs & remaining_catalog_slugs(race_data_dir))
    if collisions:
        raise ValueError(
            "road redirects collide with remaining GG catalog slugs: "
            + ", ".join(collisions)
        )


def generate_server_deletion_paths(migration_map: dict) -> list[str]:
    """Generate explicit page-directory and markdown-mirror deletion paths."""
    entries = redirected_entries(migration_map)
    page_paths = [entry["gg"]["page_path"] for entry in entries]
    markdown_paths = [entry["gg"]["markdown_mirror_path"] for entry in entries]

    if any(not _PAGE_PATH_RE.fullmatch(path) for path in page_paths):
        raise ValueError("invalid or non-explicit page path in migration map")
    if any(not _MARKDOWN_PATH_RE.fullmatch(path) for path in markdown_paths):
        raise ValueError("invalid or non-explicit markdown path in migration map")

    paths = page_paths + markdown_paths
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate server deletion path generated")
    if any("*" in path or "?" in path for path in paths):
        raise ValueError("wildcards are forbidden in the server deletion list")
    if any(KEEP_ON_GG_SLUG in path for path in paths):
        raise ValueError("Rift Valley Odyssey must not be deleted")
    return paths


def _redirect_targets(entry: dict) -> tuple[str, str]:
    action = entry["action"]
    if action == "hub_redirect":
        return ROADIE_LABS_HUB, ROADIE_LABS_HUB

    url_mapping = entry.get("url_mapping", {})
    page_target = url_mapping.get("roadie_labs_page_url")
    markdown_target = url_mapping.get("roadie_labs_markdown_mirror_url")
    if not (
        isinstance(page_target, str)
        and page_target.startswith("https://roadielabs.com/race/")
        and page_target.endswith("/")
        and isinstance(markdown_target, str)
        and markdown_target.startswith("https://roadielabs.com/race/")
        and markdown_target.endswith(".md")
    ):
        raise ValueError(
            f"missing canonical Roadie Labs targets for {entry['gg']['slug']}"
        )
    return page_target, markdown_target


def generate_redirect_rules(
    migration_map: dict,
    race_data_dir: Path = DEFAULT_RACE_DATA_DIR,
) -> list[str]:
    """Generate two explicit Apache RewriteRules for each departing GG slug."""
    assert_no_remaining_slug_collisions(migration_map, race_data_dir)

    rules = []
    for entry in redirected_entries(migration_map):
        slug = entry["gg"]["slug"]
        page_target, markdown_target = _redirect_targets(entry)
        rules.extend(
            [
                f"RewriteRule ^race/{slug}/?$ {page_target} [R=301,L]",
                f"RewriteRule ^race/{slug}\\.md$ {markdown_target} [R=301,L]",
            ]
        )
    return rules


def generate_redirect_section(
    migration_map: dict,
    race_data_dir: Path = DEFAULT_RACE_DATA_DIR,
) -> str:
    """Render the generated managed-block section, including marker comments."""
    rules = generate_redirect_rules(migration_map, race_data_dir)
    lines = [
        REDIRECT_SECTION_BEGIN,
        "# Generated from docs/specs/road-migration-map.json; do not hand-edit.",
        *rules,
        REDIRECT_SECTION_END,
    ]
    return "\n".join(lines)


def write_server_deletion_list(
    migration_map: dict,
    output_path: Path = DEFAULT_DELETION_PATH,
) -> list[str]:
    """Write the explicit deletion list and return the written paths."""
    paths = generate_server_deletion_paths(migration_map)
    Path(output_path).write_text("\n".join(paths) + "\n", encoding="utf-8")
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate approved GG road-migration build artifacts"
    )
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP_PATH)
    parser.add_argument(
        "--deletion-output",
        type=Path,
        default=DEFAULT_DELETION_PATH,
    )
    parser.add_argument(
        "--race-data-dir",
        type=Path,
        default=DEFAULT_RACE_DATA_DIR,
    )
    args = parser.parse_args()

    migration_map = load_approved_map(args.map)
    deletion_paths = write_server_deletion_list(
        migration_map, args.deletion_output
    )
    redirect_rules = generate_redirect_rules(migration_map, args.race_data_dir)
    redirect_section = generate_redirect_section(
        migration_map, args.race_data_dir
    )

    page_deletions = sum(path.endswith("/") for path in deletion_paths)
    markdown_deletions = len(deletion_paths) - page_deletions
    print(
        f"Deletion list: {len(deletion_paths)} explicit paths "
        f"({page_deletions} page directories + "
        f"{markdown_deletions} markdown mirrors)"
    )
    print(
        f"Redirects: {len(redirect_rules)} rules for "
        f"{len(redirect_rules) // 2} source slugs "
        f"({EXPECTED_ACTION_COUNTS['redirect']} paired targets + "
        f"{EXPECTED_ACTION_COUNTS['hub_redirect']} hub fallbacks)"
    )
    delta = len((redirect_section + "\n").encode("utf-8"))
    print(
        f"Estimated .htaccess size delta: {delta:,} bytes "
        f"({delta / 1024:.1f} KiB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
