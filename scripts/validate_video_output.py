#!/usr/bin/env python3
"""Validate assembled rough-cut videos for spec compliance.

Checks each video-output/<format>/<slug>/ directory against:
- Output file present (<slug>-rough.mp4)
- Duration within the brief's duration_target_range (+1s mux tolerance)
- Resolution/aspect correct for the format (9:16 Shorts, 16:9 long)
- Captions present: non-empty SRT sidecar, parseable, cues in bounds,
  monotonically ordered
- No beat overlaps or gaps in the source brief's time_ranges
- Narration kit sidecars present (teleprompter, envelope)
- Audio levels: audio stream exists, no clipping (max above -0.5 dBFS),
  not silent when a narration track was mixed

Usage:
    python scripts/validate_video_output.py                  # validate all
    python scripts/validate_video_output.py --format tier-reveal
    python scripts/validate_video_output.py --slug leadville-100
    python scripts/validate_video_output.py --strict --json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from validate_video_briefs import SHORT_FORMATS  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / "video-output"
BRIEFS_DIR = PROJECT_ROOT / "video-briefs"

RES_SHORT = (1080, 1920)
RES_LONG = (1920, 1080)
DURATION_TOLERANCE_SEC = 1.0
CLIPPING_DBFS = -0.5
SILENCE_DBFS = -60.0

SRT_TIME_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})"
)


def probe_video(path: Path) -> dict:
    """Duration, resolution and audio presence via ffprobe."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,width,height",
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    if out.returncode != 0:
        return {}
    data = json.loads(out.stdout or "{}")
    info = {"duration": float(data.get("format", {}).get("duration", 0))}
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            info["width"] = stream.get("width", 0)
            info["height"] = stream.get("height", 0)
        elif stream.get("codec_type") == "audio":
            info["has_audio"] = True
    return info


def measure_audio_levels(path: Path) -> dict:
    """mean/max volume in dBFS via the volumedetect filter."""
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-map", "0:a:0", "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )
    levels = {}
    for key in ("mean_volume", "max_volume"):
        m = re.search(rf"{key}:\s*(-?[\d.]+)\s*dB", out.stderr or "")
        if m:
            levels[key] = float(m.group(1))
    return levels


def parse_srt_cues(text: str) -> list[tuple[float, float]]:
    cues = []
    for m in SRT_TIME_RE.finditer(text):
        h1, m1, s1, ms1, h2, m2, s2, ms2 = (int(g) for g in m.groups())
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000
        end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000
        cues.append((start, end))
    return cues


def check_beat_sequence(brief: dict) -> list[str]:
    """Overlaps or gaps between consecutive beat time_ranges."""
    from assemble_video import parse_time_range
    problems = []
    prev_end = None
    for beat in brief.get("beats", []):
        try:
            start, end = parse_time_range(beat.get("time_range", ""))
        except ValueError:
            problems.append(f"beat '{beat.get('id', '?')}' bad time_range")
            continue
        if prev_end is not None:
            if start < prev_end:
                problems.append(
                    f"beat '{beat.get('id', '?')}' overlaps previous "
                    f"({start} < {prev_end})")
            elif start > prev_end:
                problems.append(
                    f"gap before beat '{beat.get('id', '?')}' "
                    f"({prev_end} -> {start})")
        prev_end = end
    return problems


def validate_output_dir(out_dir: Path) -> tuple[list[str], list[str]]:
    """Validate one assembled video directory. Returns (errors, warnings)."""
    errors, warnings = [], []
    slug = out_dir.name
    fmt = out_dir.parent.name
    prefix = f"{fmt}/{slug}"

    video = out_dir / f"{slug}-rough.mp4"
    if not video.exists():
        errors.append(f"{prefix}: missing {video.name}")
        return errors, warnings

    brief_path = BRIEFS_DIR / fmt / f"{slug}.json"
    brief = {}
    if brief_path.exists():
        with open(brief_path) as f:
            brief = json.load(f)
    else:
        warnings.append(f"{prefix}: no source brief at {brief_path}")

    info = probe_video(video)
    if not info:
        errors.append(f"{prefix}: ffprobe could not read {video.name}")
        return errors, warnings

    # ── duration ──
    target = brief.get("duration_target_range")
    if target:
        lo, hi = target
        duration = info["duration"]
        if not (lo - DURATION_TOLERANCE_SEC
                <= duration <= hi + DURATION_TOLERANCE_SEC):
            errors.append(
                f"{prefix}: duration {duration:.1f}s outside target "
                f"{lo}-{hi}s")

    # ── resolution / aspect ──
    expected = RES_SHORT if fmt in SHORT_FORMATS else RES_LONG
    actual = (info.get("width", 0), info.get("height", 0))
    if actual != expected:
        errors.append(
            f"{prefix}: resolution {actual[0]}x{actual[1]} != "
            f"{expected[0]}x{expected[1]}")

    # ── captions ──
    srt = out_dir / f"{slug}.srt"
    if not srt.exists() or not srt.read_text().strip():
        errors.append(f"{prefix}: captions missing or empty ({srt.name})")
    else:
        cues = parse_srt_cues(srt.read_text())
        if not cues:
            errors.append(f"{prefix}: SRT has no parseable cues")
        else:
            last_end = 0.0
            for start, end in cues:
                if end <= start:
                    errors.append(f"{prefix}: SRT cue with end <= start")
                    break
                if start < last_end - 0.001:
                    errors.append(f"{prefix}: SRT cues not monotonic")
                    break
                last_end = end
            if cues and cues[-1][1] > info["duration"] + 0.5:
                warnings.append(
                    f"{prefix}: last caption ends after video "
                    f"({cues[-1][1]:.1f}s > {info['duration']:.1f}s)")

    # ── beat sequence ──
    if brief:
        for problem in check_beat_sequence(brief):
            errors.append(f"{prefix}: {problem}")

    # ── narration kit sidecars ──
    for sidecar in (f"{slug}-teleprompter.md", f"{slug}-envelope.json"):
        if not (out_dir / sidecar).exists():
            warnings.append(f"{prefix}: missing sidecar {sidecar}")

    # ── audio levels ──
    if not info.get("has_audio"):
        errors.append(f"{prefix}: no audio stream")
    else:
        levels = measure_audio_levels(video)
        max_vol = levels.get("max_volume")
        mean_vol = levels.get("mean_volume")
        if max_vol is not None and max_vol > CLIPPING_DBFS:
            errors.append(
                f"{prefix}: audio clipping (max {max_vol} dBFS)")
        report_path = out_dir / f"{slug}-report.json"
        narrated = False
        if report_path.exists():
            with open(report_path) as f:
                narrated = bool(json.load(f).get("narration"))
        if narrated and mean_vol is not None and mean_vol < SILENCE_DBFS:
            errors.append(
                f"{prefix}: narration was mixed but output is silent "
                f"(mean {mean_vol} dBFS)")

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(
        description="Validate assembled rough-cut videos.")
    parser.add_argument("--format", help="Only validate this format")
    parser.add_argument("--slug", help="Only validate this slug")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 on any warning")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON report")
    parser.add_argument("--dir", default=str(OUTPUT_DIR),
                        help="Output directory root")
    args = parser.parse_args()

    root = Path(args.dir)
    if not root.exists():
        print(f"ERROR: output directory not found: {root}", file=sys.stderr)
        sys.exit(1)

    out_dirs = []
    for fmt_dir in sorted(root.iterdir()):
        if not fmt_dir.is_dir():
            continue
        if args.format and fmt_dir.name != args.format:
            continue
        for slug_dir in sorted(fmt_dir.iterdir()):
            if not slug_dir.is_dir():
                continue
            if args.slug and slug_dir.name != args.slug:
                continue
            out_dirs.append(slug_dir)

    if not out_dirs:
        print("No assembled videos found.", file=sys.stderr)
        sys.exit(1)

    total_errors, total_warnings = [], []
    for out_dir in out_dirs:
        errors, warnings = validate_output_dir(out_dir)
        total_errors.extend(errors)
        total_warnings.extend(warnings)

    if args.json:
        print(json.dumps({
            "validated": len(out_dirs),
            "errors": len(total_errors),
            "warnings": len(total_warnings),
            "error_details": total_errors[:50],
            "warning_details": total_warnings[:50],
        }, indent=2))
    else:
        if total_errors:
            print(f"\nERRORS ({len(total_errors)}):")
            for e in total_errors:
                print(f"  {e}")
        if total_warnings:
            print(f"\nWARNINGS ({len(total_warnings)}):")
            for w in total_warnings[:20]:
                print(f"  {w}")
            if len(total_warnings) > 20:
                print(f"  ... and {len(total_warnings) - 20} more")
        status = "PASS" if not total_errors else "FAIL"
        print(f"\n{status}: {len(out_dirs)} videos validated, "
              f"{len(total_errors)} errors, {len(total_warnings)} warnings.")

    if total_errors or (args.strict and total_warnings):
        sys.exit(1)


if __name__ == "__main__":
    main()
