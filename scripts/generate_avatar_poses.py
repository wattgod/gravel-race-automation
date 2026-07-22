#!/usr/bin/env python3
"""Generate the avatar pose library via the Runware API (Workstream A).

Character consistency comes from FLUX.1 Kontext [dev] reference-image
editing: every pose is generated FROM the canonical character art, not from
a text description of the character. Pipeline per pose:

    reference PNG ──Kontext (pose prompt)──> posed image
                  ──Bria RMBG v2.0────────> transparent PNG
                  ──> assets/avatar/<pose>.png

Motion loops (--loops): image-to-video with the SAME pose image pinned as
both first and last frame, so the clip loops seamlessly. Loops are
generated on a solid green background (mp4 carries no alpha); the
assembler chroma-keys them out at composite time.

    assets/avatar/<pose>.png ──image-to-video──> assets/avatar/loops/<pose>.mp4

Usage:
    python scripts/generate_avatar_poses.py --reference assets/avatar/source/character.png
    python scripts/generate_avatar_poses.py --poses shocked,thinking --reference ...
    python scripts/generate_avatar_poses.py --t1-only --reference ...   # 6 poses the T1 batch needs
    python scripts/generate_avatar_poses.py --loops                     # animate existing PNGs
    python scripts/generate_avatar_poses.py --dry-run ...               # print tasks + cost, no spend

Repeatable by design: --skip-existing makes re-runs only fill gaps, and new
poses are one dict entry away.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from runware_client import (  # noqa: E402
    MODEL_BG_REMOVAL,
    MODEL_FLUX_KONTEXT_DEV,
    MODEL_VIDEO_DEFAULT,
    RunwareError,
    download,
    image_to_data_uri,
    new_uuid,
    poll_async,
    request,
)

AVATAR_DIR = PROJECT_ROOT / "assets" / "avatar"
SOURCE_DIR = AVATAR_DIR / "source"
LOOPS_DIR = AVATAR_DIR / "loops"

# Shared style anchor for every pose prompt. The reference image carries
# the character; the prompt only describes the new pose/expression.
STYLE = ("Same cartoon character, identical face, mustache, outfit and "
         "proportions, flat South Park style cutout, clean vector edges, "
         "full body visible, centered, plain solid white background")

# The full pose vocabulary: the 16 poses from the production plan plus the
# two extra poses ('excited', 'mind_blown') that existing briefs reference.
POSES = {
    "shocked": "eyes wide and mouth open in exaggerated shock, hands on cheeks",
    "chef_kiss": "kissing fingertips like a chef, eyes closed in satisfaction",
    "facepalm": "palm covering face in exasperated disappointment",
    "mustache_twirl": "smugly twirling one end of the mustache, sly grin",
    "pointing": "pointing directly at the viewer with one confident finger",
    "presenting": "both arms extended presenting something to the side",
    "skeptical": "one eyebrow raised, arms crossed, unconvinced expression",
    "suffering": "grimacing in agony, hunched over, sweat drops flying",
    "thinking": "hand on chin, eyes up, deep in thought",
    "thumbs_up": "big approving thumbs up, satisfied grin",
    "versus": "fists raised in a boxing stance, competitive scowl",
    "dramatic": "arm thrown across forehead in theatrical despair",
    "counting": "counting on raised fingers, explanatory look",
    "shrug": "exaggerated shrug, palms up, indifferent face",
    "leaning_in": "leaning toward the viewer conspiratorially, hand beside mouth",
    "mic_drop": "dropping a microphone, looking away, triumphant",
    "excited": "jumping with both fists in the air, ecstatic open-mouth smile",
    "mind_blown": "hands at temples miming an explosion, awestruck face",
}

# The 6 poses the 25-race T1 tier-reveal batch actually uses.
T1_POSES = ["excited", "pointing", "presenting", "shocked", "skeptical",
            "thinking"]

LOOP_PROMPT = ("subtle idle animation of this cartoon character: gentle "
               "breathing, occasional blink, slight sway, flat 2D style "
               "preserved, character stays in place, solid bright green "
               "background, no camera movement")

COST_PER_IMAGE = 0.0105 * 2  # Kontext + background removal, ~rounded
COST_PER_LOOP = 0.35         # video gen, order-of-magnitude


def find_reference(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise SystemExit(f"reference image not found: {path}")
        return path
    candidates = sorted(SOURCE_DIR.glob("*.png")) + sorted(
        SOURCE_DIR.glob("*.jpg"))
    if not candidates:
        raise SystemExit(
            f"No reference art in {SOURCE_DIR}. Export the character art "
            "from RunDiffusion (or pass --reference path/to/character.png).")
    return candidates[0]


def generate_pose(pose: str, prompt: str, reference_uri: str) -> Path:
    """Kontext pose edit + background removal -> transparent pose PNG."""
    gen_uuid = new_uuid()
    data = request([{
        "taskType": "imageInference",
        "taskUUID": gen_uuid,
        "model": MODEL_FLUX_KONTEXT_DEV,
        "positivePrompt": f"{prompt}. {STYLE}",
        "width": 1024,
        "height": 1024,
        "steps": 28,
        "outputFormat": "PNG",
        "numberResults": 1,
        "inputs": {"referenceImages": [reference_uri]},
    }])
    posed = next((d for d in data if d.get("taskUUID") == gen_uuid), {})
    image_ref = posed.get("imageUUID") or posed.get("imageURL")
    if not image_ref:
        raise RunwareError(f"{pose}: no image in response: {posed}")

    rm_uuid = new_uuid()
    data = request([{
        "taskType": "removeBackground",
        "taskUUID": rm_uuid,
        "model": MODEL_BG_REMOVAL,
        "outputFormat": "PNG",
        "inputs": {"image": image_ref},
    }])
    cut = next((d for d in data if d.get("taskUUID") == rm_uuid), {})
    url = cut.get("imageURL")
    if not url:
        raise RunwareError(f"{pose}: background removal failed: {cut}")
    return download(url, AVATAR_DIR / f"{pose}.png")


def generate_loop(pose: str, model: str = MODEL_VIDEO_DEFAULT,
                  duration: int = 5) -> Path:
    """Image-to-video loop: same pose pinned as first AND last frame."""
    png = AVATAR_DIR / f"{pose}.png"
    if not png.exists():
        raise RunwareError(f"{pose}: generate the PNG first ({png})")
    uri = image_to_data_uri(png)
    task_uuid = new_uuid()
    request([{
        "taskType": "videoInference",
        "taskUUID": task_uuid,
        "model": model,
        "positivePrompt": LOOP_PROMPT,
        "duration": duration,
        "frameImages": [
            {"inputImage": uri, "frame": 0},
            {"inputImage": uri, "frame": "last"},
        ],
    }])
    result = poll_async(task_uuid)
    url = result.get("videoURL")
    if not url:
        raise RunwareError(f"{pose}: no videoURL in result: {result}")
    return download(url, LOOPS_DIR / f"{pose}.mp4")


def main():
    parser = argparse.ArgumentParser(
        description="Generate avatar poses + motion loops via Runware.")
    parser.add_argument("--poses", help="Comma-separated pose names")
    parser.add_argument("--t1-only", action="store_true",
                        help=f"Only the T1 batch poses: {', '.join(T1_POSES)}")
    parser.add_argument("--reference",
                        help="Canonical character art (default: first image "
                             "in assets/avatar/source/)")
    parser.add_argument("--loops", action="store_true",
                        help="Generate motion loops for existing pose PNGs")
    parser.add_argument("--video-model", default=MODEL_VIDEO_DEFAULT)
    parser.add_argument("--skip-existing", action="store_true", default=True)
    parser.add_argument("--force", dest="skip_existing", action="store_false",
                        help="Regenerate even if the file exists")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the plan and cost estimate, spend nothing")
    args = parser.parse_args()

    if args.poses:
        selected = []
        for name in args.poses.split(","):
            name = name.strip()
            if name not in POSES:
                parser.error(f"unknown pose '{name}'. "
                             f"Known: {', '.join(POSES)}")
            selected.append(name)
    elif args.t1_only:
        selected = list(T1_POSES)
    else:
        selected = list(POSES)

    if args.loops:
        todo = [p for p in selected
                if not (args.skip_existing and (LOOPS_DIR / f"{p}.mp4").exists())
                and (AVATAR_DIR / f"{p}.png").exists()]
        missing_png = [p for p in selected
                       if not (AVATAR_DIR / f"{p}.png").exists()]
        if missing_png:
            print(f"skipping {len(missing_png)} poses with no PNG yet: "
                  f"{', '.join(missing_png)}")
        print(f"Loops to generate: {len(todo)} "
              f"(~${len(todo) * COST_PER_LOOP:.2f})")
        if args.dry_run:
            return
        for pose in todo:
            print(f"▸ loop {pose}")
            path = generate_loop(pose, model=args.video_model)
            print(f"  ✓ {path.relative_to(PROJECT_ROOT)}")
        return

    todo = [p for p in selected
            if not (args.skip_existing and (AVATAR_DIR / f"{p}.png").exists())]
    print(f"Poses to generate: {len(todo)} "
          f"(~${len(todo) * COST_PER_IMAGE:.2f})")
    if args.dry_run:
        for pose in todo:
            print(f"  {pose}: {POSES[pose]}")
        return
    reference_uri = image_to_data_uri(find_reference(args.reference))
    failures = []
    for pose in todo:
        print(f"▸ {pose}")
        try:
            path = generate_pose(pose, POSES[pose], reference_uri)
            print(f"  ✓ {path.relative_to(PROJECT_ROOT)}")
        except RunwareError as e:
            print(f"  ✗ {e}")
            failures.append(pose)
    if failures:
        print(f"\nFailed: {', '.join(failures)} — re-run to retry "
              "(--skip-existing keeps finished poses)")
        sys.exit(1)


if __name__ == "__main__":
    main()
