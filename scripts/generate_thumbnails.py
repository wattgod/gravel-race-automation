#!/usr/bin/env python3
"""Batch-generate video thumbnails from brief thumbnail_prompts via Runware.

Each brief carries a Midjourney-style thumbnail_prompt
("... --ar 9:16 --cref [CHARACTER_URL]"). This script adapts it for
FLUX.1 Kontext [dev]: Midjourney flags are stripped, --ar picks the output
size, and --cref becomes the character reference image (true character
consistency instead of Midjourney's cref).

Usage:
    python scripts/generate_thumbnails.py --batch tier-reveal --tier T1
    python scripts/generate_thumbnails.py --brief video-briefs/tier-reveal/leadville-100.json
    python scripts/generate_thumbnails.py --batch tier-reveal --tier T1 --dry-run

Output: assets/thumbnails/<slug>.png
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from runware_client import (  # noqa: E402
    MODEL_FLUX_KONTEXT_DEV,
    RunwareError,
    download,
    image_to_data_uri,
    new_uuid,
    request,
)
from assemble_video import find_briefs, parse_tier  # noqa: E402
from generate_avatar_poses import find_reference  # noqa: E402

THUMBS_DIR = PROJECT_ROOT / "assets" / "thumbnails"

# Kontext-supported sizes nearest to the two aspect ratios used by briefs
SIZE_BY_AR = {"9:16": (752, 1392), "16:9": (1392, 752)}
DEFAULT_SIZE = (1024, 1024)

MJ_FLAG_RE = re.compile(r"--\w+(?:\s+\[?[^\s\]]+\]?)?")
STYLE_SUFFIX = (", bold flat poster design, high contrast, clean shapes, "
                "huge readable text, no watermark")

COST_PER_IMAGE = 0.0105


def adapt_prompt(thumbnail_prompt: str) -> tuple[str, tuple[int, int]]:
    """Midjourney prompt -> (FLUX prompt, (width, height))."""
    size = DEFAULT_SIZE
    for ar, dims in SIZE_BY_AR.items():
        if f"--ar {ar}" in thumbnail_prompt:
            size = dims
            break
    prompt = MJ_FLAG_RE.sub("", thumbnail_prompt)
    prompt = re.sub(r"\s{2,}", " ", prompt).strip().rstrip(",")
    return prompt + STYLE_SUFFIX, size


def generate_thumbnail(brief: dict, reference_uri: str) -> Path:
    prompt, (width, height) = adapt_prompt(brief.get("thumbnail_prompt", ""))
    task_uuid = new_uuid()
    data = request([{
        "taskType": "imageInference",
        "taskUUID": task_uuid,
        "model": MODEL_FLUX_KONTEXT_DEV,
        "positivePrompt": prompt,
        "width": width,
        "height": height,
        "steps": 28,
        "outputFormat": "PNG",
        "numberResults": 1,
        "inputs": {"referenceImages": [reference_uri]},
    }])
    result = next((d for d in data if d.get("taskUUID") == task_uuid), {})
    url = result.get("imageURL")
    if not url:
        raise RunwareError(f"{brief['slug']}: no imageURL: {result}")
    return download(url, THUMBS_DIR / f"{brief['slug']}.png")


def main():
    parser = argparse.ArgumentParser(
        description="Generate thumbnails from brief thumbnail_prompts.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--brief", type=Path)
    source.add_argument("--batch", metavar="FORMAT")
    parser.add_argument("--tier", help="With --batch: only this tier")
    parser.add_argument("--reference",
                        help="Character art (default: assets/avatar/source/)")
    parser.add_argument("--skip-existing", action="store_true", default=True)
    parser.add_argument("--force", dest="skip_existing", action="store_false")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.brief:
        paths = [args.brief]
    else:
        tier = parse_tier(args.tier) if args.tier else None
        paths = find_briefs(args.batch, tier)
    if args.limit:
        paths = paths[: args.limit]

    briefs = []
    for path in paths:
        with open(path) as f:
            brief = json.load(f)
        out = THUMBS_DIR / f"{brief['slug']}.png"
        if args.skip_existing and out.exists():
            continue
        briefs.append(brief)

    print(f"Thumbnails to generate: {len(briefs)} "
          f"(~${len(briefs) * COST_PER_IMAGE:.2f})")
    if args.dry_run:
        for brief in briefs:
            prompt, size = adapt_prompt(brief.get("thumbnail_prompt", ""))
            print(f"  {brief['slug']} {size[0]}x{size[1]}: {prompt[:90]}…")
        return

    reference_uri = image_to_data_uri(find_reference(args.reference))
    failures = []
    for brief in briefs:
        print(f"▸ {brief['slug']}")
        try:
            path = generate_thumbnail(brief, reference_uri)
            print(f"  ✓ {path.relative_to(PROJECT_ROOT)}")
        except RunwareError as e:
            print(f"  ✗ {e}")
            failures.append(brief["slug"])
    if failures:
        print(f"\nFailed: {', '.join(failures)} — re-run to retry")
        sys.exit(1)


if __name__ == "__main__":
    main()
