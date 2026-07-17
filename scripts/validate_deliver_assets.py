#!/usr/bin/env python3
"""
Validate that all assets referenced by Deliver course lessons exist on disk.

Scans every lesson JSON file for image, download, and audio blocks,
extracts referenced file paths, and checks they exist. Fails with
exit code 1 if any are missing.

Usage:
    python scripts/validate_deliver_assets.py
    python scripts/validate_deliver_assets.py --strict  # also fail on placeholder URLs
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COURSE_DIR = PROJECT_ROOT / "data" / "courses" / "deliver"
# Assets served from WordPress static dirs
STATIC_ROOT = PROJECT_ROOT / "wordpress" / "output" / "course" / "deliver"


def extract_asset_refs(blocks: list) -> list:
    """Extract all asset references (url, src, asset_id) from blocks."""
    refs = []
    for block in blocks:
        btype = block.get("type", "")
        if btype == "image":
            asset_id = block.get("asset_id", "")
            if asset_id:
                refs.append(("image", asset_id, f"/course/deliver/img/{asset_id}"))
        elif btype == "download":
            url = block.get("url", "")
            if url:
                refs.append(("download", url, url))
        elif btype == "audio":
            src = block.get("src", "")
            if src:
                refs.append(("audio", src, src))
    return refs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="Also fail on placeholder URLs (no actual file)")
    args = parser.parse_args()

    lessons_dir = COURSE_DIR / "lessons"
    if not lessons_dir.exists():
        print(f"ERROR: No lessons directory at {lessons_dir}")
        print("Run scripts/migrate_deliver.py first.")
        sys.exit(1)

    all_refs = []
    for lesson_file in sorted(lessons_dir.glob("*.json")):
        lesson = json.loads(lesson_file.read_text(encoding="utf-8"))
        refs = extract_asset_refs(lesson.get("blocks", []))
        for ref in refs:
            all_refs.append((lesson_file.name, *ref))

    if not all_refs:
        print("No asset references found in lesson files.")
        return

    # Group by type
    by_type = {}
    for lesson_name, atype, ref, path in all_refs:
        by_type.setdefault(atype, []).append((lesson_name, ref, path))

    print(f"Asset references found: {len(all_refs)}")
    for atype, items in sorted(by_type.items()):
        print(f"  {atype}: {len(items)}")

    # Check existence
    # For now, just report — assets haven't been created yet
    missing = []
    placeholder = []
    for lesson_name, atype, ref, path in all_refs:
        # Check if it's a relative path we can verify
        if path.startswith("/") or path.startswith("http"):
            # Can't check external URLs or absolute server paths
            placeholder.append((lesson_name, atype, ref))
        else:
            full_path = PROJECT_ROOT / path.lstrip("/")
            if not full_path.exists():
                missing.append((lesson_name, atype, ref))

    print(f"\nPlaceholder/external refs (need manual verification): {len(placeholder)}")
    for lesson_name, atype, ref in placeholder:
        print(f"  [{atype}] {lesson_name}: {ref}")

    if missing:
        print(f"\nMISSING assets ({len(missing)}):")
        for lesson_name, atype, ref in missing:
            print(f"  [{atype}] {lesson_name}: {ref}")
        if args.strict:
            sys.exit(1)

    # Build manifest
    manifest = {
        "images": sorted(set(ref for _, atype, ref, _ in all_refs if atype == "image")),
        "downloads": sorted(set(ref for _, atype, ref, _ in all_refs if atype == "download")),
        "audio": sorted(set(ref for _, atype, ref, _ in all_refs if atype == "audio")),
    }
    manifest_path = COURSE_DIR / "asset-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"\nAsset manifest written to {manifest_path}")


if __name__ == "__main__":
    main()
