#!/usr/bin/env python3
"""Report relevance-score coverage for race-page YouTube stills.

The renderer only admits ``video-*`` photos with ``ai_relevance >= 4`` and
shows at most two. Trusted non-video photos are intentionally outside this
gate. This audit makes legacy coverage and races that would lose every video
still visible before a catalog sync.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "race-data"


def parse_score(raw) -> float | None:
    """Return a numeric score, or None for missing/malformed values."""
    if raw is None or raw == "" or isinstance(raw, bool):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def scan_photo_coverage(data_dir: Path) -> dict:
    """Scan race JSON files and return stable aggregate coverage metrics."""
    report = {
        "race_files": 0,
        "races_with_video_stills": 0,
        "races_fully_scored": 0,
        "races_partially_scored": 0,
        "races_with_no_scored_stills": 0,
        "races_losing_all_video_stills": [],
        "video_stills": 0,
        "video_stills_scored": 0,
        "video_stills_passing": 0,
    }

    for path in sorted(data_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        race = payload.get("race", payload)
        report["race_files"] += 1
        stills = [
            photo for photo in race.get("photos", [])
            if str(photo.get("type", "")).startswith("video-")
        ]
        if not stills:
            continue

        report["races_with_video_stills"] += 1
        scores = [parse_score(photo.get("ai_relevance")) for photo in stills]
        scored = sum(score is not None for score in scores)
        passing = sum(score is not None and score >= 4 for score in scores)
        report["video_stills"] += len(stills)
        report["video_stills_scored"] += scored
        report["video_stills_passing"] += passing

        if scored == len(stills):
            report["races_fully_scored"] += 1
        elif scored:
            report["races_partially_scored"] += 1
        else:
            report["races_with_no_scored_stills"] += 1
        if passing == 0:
            report["races_losing_all_video_stills"].append(path.stem)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument(
        "--fail-on-unscored",
        action="store_true",
        help="Return non-zero when any video still lacks a relevance score.",
    )
    args = parser.parse_args()
    report = scan_photo_coverage(args.data_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.fail_on_unscored and report["video_stills_scored"] < report["video_stills"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
