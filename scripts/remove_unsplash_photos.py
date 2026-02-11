#!/usr/bin/env python3
"""Remove all `unsplash_photos` (plural) fields from race profile JSONs.

The field lives at `race.unsplash_photos` inside each profile.
Does NOT touch `unsplash_photo` (singular).
"""

import json
from pathlib import Path

RACE_DATA_DIR = Path(__file__).resolve().parent.parent / "race-data"


def remove_key_recursive(obj, target_key):
    """Remove target_key from obj and all nested dicts/lists. Returns True if any removed."""
    removed = False
    if isinstance(obj, dict):
        if target_key in obj:
            del obj[target_key]
            removed = True
        for v in obj.values():
            if remove_key_recursive(v, target_key):
                removed = True
    elif isinstance(obj, list):
        for item in obj:
            if remove_key_recursive(item, target_key):
                removed = True
    return removed


def main():
    modified = 0
    scanned = 0

    for filepath in sorted(RACE_DATA_DIR.glob("*.json")):
        scanned += 1
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if remove_key_recursive(data, "unsplash_photos"):
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            modified += 1

    print(f"Scanned {scanned} files, modified {modified} (removed unsplash_photos)")


if __name__ == "__main__":
    main()
