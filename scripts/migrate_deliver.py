#!/usr/bin/env python3
"""
Migrate deliver.json from endure-mind format to Glide Labs course format.

Reads:  ~/endure-mind/course/deliver.json
Writes: data/courses/deliver/course.json
        data/courses/deliver/lessons/{module}-{lesson}-{slug}.json

Usage:
    python scripts/migrate_deliver.py
    python scripts/migrate_deliver.py --dry-run
"""

import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SOURCE_PATH = Path.home() / "endure-mind" / "course" / "deliver.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "courses" / "deliver"
LESSONS_DIR = OUTPUT_DIR / "lessons"

# ── Variant maps ──────────────────────────────────────────────

CALLOUT_VARIANT_MAP = {
    "highlight": "highlight",
    "info": "info",
    "tip": "tip",
    "quote": "quote",
}

# Block types we know how to migrate
KNOWN_BLOCK_TYPES = {
    "text", "callout", "accordion", "tabs", "timeline", "process",
    "quiz", "scenario", "flashcard", "image", "download", "audio",
    "sorting",
}


# ── Helper functions ──────────────────────────────────────────


def extract_asset_id(src: str) -> str:
    """Strip path prefix and extension: img/deliver/yerkes-dodson.svg → yerkes-dodson"""
    basename = os.path.splitext(os.path.basename(src))[0]
    return basename


def migrate_block(block: dict) -> dict:
    """Transform a single deliver.json block to Glide Labs format.

    Returns the migrated block dict. Raises ValueError for unknown types.
    """
    btype = block["type"]

    if btype not in KNOWN_BLOCK_TYPES:
        raise ValueError(f"Unknown block type: '{btype}'")

    # 1. text → prose
    if btype == "text":
        return {"type": "prose", "content": block["content"]}

    # 2. callout → callout
    if btype == "callout":
        variant = block.get("variant", "highlight")
        style = CALLOUT_VARIANT_MAP.get(variant, variant)
        result = {"type": "callout", "style": style, "content": block["content"]}
        if "attribution" in block:
            result["attribution"] = block["attribution"]
        return result

    # 3. accordion → accordion
    if btype == "accordion":
        items = [
            {"title": p["title"], "content": p["content"]}
            for p in block["panels"]
        ]
        return {"type": "accordion", "items": items}

    # 4. tabs → tabs (pass through)
    if btype == "tabs":
        return block.copy()

    # 5. timeline → timeline
    if btype == "timeline":
        events = block.get("events", block.get("stages", []))
        steps = [
            {"label": s["title"], "content": s["content"]}
            for s in events
        ]
        return {
            "type": "timeline",
            "title": block.get("title", ""),
            "steps": steps,
        }

    # 6. process → process_list
    if btype == "process":
        items = [
            {"label": s["title"], "detail": s["content"]}
            for s in block["steps"]
        ]
        return {"type": "process_list", "items": items}

    # 7. quiz → depends on variant
    if btype == "quiz":
        variant = block.get("variant", "")

        # matching
        if variant == "matching":
            return {
                "type": "matching",
                "question": block["question"],
                "pairs": block["pairs"],
                "explanation": block.get("feedback", {}).get("correct", ""),
            }

        # fill-in-the-blank
        if variant == "fill-in-the-blank":
            return {
                "type": "fill_in_blank",
                "question": block["question"],
                "answers": block.get("answers", []),
                "explanation": block.get("feedback", {}).get("correct", ""),
            }

        # sorting (quiz variant)
        if variant == "sorting":
            return {
                "type": "sorting",
                "prompt": block["question"],
                "categories": block["categories"],
                "items": block["items"],
                "feedback": block.get("feedback", {}),
            }

        # multiple-response → knowledge_check (renderer handles multiple correct)
        # default/no variant → knowledge_check
        return {
            "type": "knowledge_check",
            "question": block["question"],
            "explanation": block.get("feedback", {}).get("correct", ""),
            "options": [
                {"text": o["text"], "correct": o.get("correct", False)}
                for o in block["options"]
            ],
        }

    # 8. scenario → scenario
    if btype == "scenario":
        return {
            "type": "scenario",
            "prompt": block["prompt"],
            "options": [
                {
                    "label": o["label"],
                    "result": o["consequence"],
                    "best": o.get("best", False),
                }
                for o in block["options"]
            ],
        }

    # 9. flashcard → flashcard
    if btype == "flashcard":
        return {
            "type": "flashcard",
            "title": block.get("title", ""),
            "cards": [
                {
                    "front": c.get("front", c.get("term", "")),
                    "back": c.get("back", c.get("definition", "")),
                }
                for c in block["cards"]
            ],
        }

    # 10. image → image
    if btype == "image":
        return {
            "type": "image",
            "asset_id": extract_asset_id(block["src"]),
            "alt": block.get("alt", ""),
            "caption": block.get("caption", ""),
        }

    # 11. download → download (pass through with field mapping)
    if btype == "download":
        return {
            "type": "download",
            "title": block.get("title", "Download"),
            "url": block.get("file", block.get("url", "")),
            "description": block.get("description", ""),
        }

    # 12. audio → audio (pass through with field mapping)
    if btype == "audio":
        return {
            "type": "audio",
            "title": block.get("title", "Audio"),
            "src": block.get("file", block.get("src", "")),
            "description": block.get("description", ""),
            "duration": block.get("duration", ""),
        }

    # 13. sorting (top-level block, not quiz variant) → sorting
    if btype == "sorting":
        return {
            "type": "sorting",
            "prompt": block["prompt"],
            "categories": block["categories"],
            "items": block["items"],
            "feedback": block.get("feedback", {}),
        }

    # Should never reach here due to KNOWN_BLOCK_TYPES check
    raise ValueError(f"Unhandled block type: '{btype}'")


def build_course_json(source: dict) -> dict:
    """Build the top-level course.json from deliver.json source data."""
    course = source["course"]
    modules = []

    for mod_idx, mod in enumerate(course["modules"]):
        lessons = []
        for les_idx, les in enumerate(mod["lessons"]):
            lesson_filename = f"lessons/{mod_idx + 1:02d}-{les_idx + 1:02d}-{les['slug']}.json"
            lessons.append({
                "id": les["slug"],
                "title": les["title"],
                "file": lesson_filename,
            })
        modules.append({
            "id": mod["slug"],
            "title": mod["title"],
            "lessons": lessons,
        })

    total_lessons = sum(len(m["lessons"]) for m in course["modules"])

    return {
        "id": "deliver",
        "title": "Deliver: Unlock Your Brain",
        "subtitle": "Get out of your own way.",
        "description": (
            f"A 6-module sport psychology course for endurance athletes. "
            f"{total_lessons} lessons, 8 guided audio exercises, downloadable tools. "
            f"Built on research. Delivered by The Stoic Coach."
        ),
        "price_usd": 79,
        "stripe_payment_link": "",
        "stripe_price_id": "",
        "theme": "clean-pro",
        "instructor": {
            "name": "Matt Rowe",
            "title": "Founder, Endure Labs",
            "bio": (
                "Sport psychology practitioner, endurance coach, and founder of "
                "Endure Labs. Built Deliver from the research and 15+ years of "
                "coaching athletes through the mental side of endurance sport."
            ),
        },
        "what_youll_learn": [
            "How your brain sabotages and supports endurance performance",
            "Build an athletic identity that doesn't crack under pressure",
            "Visualization, self-talk, and mental imagery techniques backed by research",
            "Flow states, clutch performance, and motivation mechanics",
            "A complete Race Day protocol from night-before to post-race debrief",
            "Resilience tools for injury, burnout, and setbacks",
        ],
        "modules": modules,
        "meta_description": (
            "Sport psychology course for endurance athletes. 6 modules, "
            f"{total_lessons} lessons, guided exercises. Learn to manage your "
            "brain under pressure. $79."
        ),
        "og_image": "deliver-og.png",
        "noindex": True,
        "status": "active",
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Migrate deliver.json to Glide Labs format")
    parser.add_argument("--dry-run", action="store_true", help="Print summary without writing files")
    args = parser.parse_args()

    # Load source
    if not SOURCE_PATH.exists():
        print(f"ERROR: Source file not found: {SOURCE_PATH}", file=sys.stderr)
        sys.exit(1)

    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    course = source["course"]

    # Stats tracking
    type_counts = {}
    total_blocks = 0
    warnings = []

    # Validate all blocks first (fail loudly on unknown types)
    for mod_idx, mod in enumerate(course["modules"]):
        for les_idx, les in enumerate(mod["lessons"]):
            for blk_idx, block in enumerate(les["blocks"]):
                btype = block["type"]
                if btype not in KNOWN_BLOCK_TYPES:
                    print(
                        f"ERROR: Unknown block type '{btype}' in module {mod_idx + 1} "
                        f"({mod['title']}), lesson {les_idx + 1} ({les['title']}), "
                        f"block {blk_idx + 1}",
                        file=sys.stderr,
                    )
                    sys.exit(1)

    # Build course.json
    course_json = build_course_json(source)

    # Migrate all lessons
    lesson_files = {}  # path → data
    for mod_idx, mod in enumerate(course["modules"]):
        for les_idx, les in enumerate(mod["lessons"]):
            migrated_blocks = []
            for block in les["blocks"]:
                btype = block["type"]
                # Track original type (before quiz variant split)
                variant = block.get("variant", "")
                if btype == "quiz" and variant:
                    track_key = f"quiz:{variant}"
                else:
                    track_key = btype
                type_counts[track_key] = type_counts.get(track_key, 0) + 1
                total_blocks += 1

                migrated = migrate_block(block)
                migrated_blocks.append(migrated)

            lesson_data = {
                "id": les["slug"],
                "title": les["title"],
                "description": les.get("description", ""),
                "blocks": migrated_blocks,
            }

            filename = f"{mod_idx + 1:02d}-{les_idx + 1:02d}-{les['slug']}.json"
            lesson_files[filename] = lesson_data

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"  DELIVER MIGRATION SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Source: {SOURCE_PATH}")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Modules: {len(course['modules'])}")
    print(f"  Lessons: {len(lesson_files)}")
    print(f"  Total blocks: {total_blocks}")
    print(f"\n  Blocks by type:")
    for key in sorted(type_counts.keys()):
        print(f"    {key:30s} {type_counts[key]:>4d}")
    if warnings:
        print(f"\n  Warnings:")
        for w in warnings:
            print(f"    {w}")
    print(f"{'=' * 60}\n")

    if args.dry_run:
        print("  DRY RUN — no files written.")
        return

    # Write files
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LESSONS_DIR.mkdir(parents=True, exist_ok=True)

    # Write course.json
    course_path = OUTPUT_DIR / "course.json"
    course_path.write_text(json.dumps(course_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Wrote: {course_path}")

    # Write lesson files
    for filename, data in lesson_files.items():
        lesson_path = LESSONS_DIR / filename
        lesson_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  Wrote: {len(lesson_files)} lesson files to {LESSONS_DIR}/")
    print(f"\n  Migration complete.")


if __name__ == "__main__":
    main()
