#!/usr/bin/env python3
"""Extract high-quality still frames and course preview GIFs from YouTube race videos.

Uses yt-dlp + ffmpeg + Pillow heuristics. No AI API keys needed.

Tier-aware:
  T1: up to 5 GIFs from up to 4 videos (capture wild moments)
  T2: up to 3 GIFs from up to 3 videos
  T3-T4: 1 GIF from top 2 videos

Usage:
    python scripts/youtube_screenshots.py --slug unbound-200
    python scripts/youtube_screenshots.py --auto 297
    python scripts/youtube_screenshots.py --auto 10 --dry-run
    python scripts/youtube_screenshots.py --force --slug badlands
    python scripts/youtube_screenshots.py --status
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import warnings
from datetime import date
from pathlib import Path

warnings.filterwarnings("ignore", message=".*getdata.*deprecated.*", category=DeprecationWarning)

try:
    from PIL import Image, ImageFilter, ImageStat
except ImportError:
    sys.exit("Pillow is required: pip install Pillow")

# ── Paths ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "race-data"
PHOTOS_DIR = PROJECT_ROOT / "race-photos"
PROGRESS_FILE = PHOTOS_DIR / "_progress.json"
LOG_FILE = PHOTOS_DIR / "_extract.log"

# ── Constants ──────────────────────────────────────────────────────────────
MIN_DURATION_SEC = 180       # 3 minutes
MAX_DURATION_SEC = 7200      # 2 hours
CLIP_SECONDS = 3
PHOTO_WIDTH = 1200
PHOTO_HEIGHT = 675
GIF_WIDTH = 400
GIF_HEIGHT = 225
JPEG_QUALITY = 85
GIF_FPS = 8
SUBPROCESS_TIMEOUT = 120     # seconds

VALID_PHOTO_TYPES = {"video-1", "video-2", "video-3", "preview-gif",
                     "street-1", "street-2", "landscape", "map"}

# Hero priority (higher index = lower priority)
HERO_PRIORITY = ["street-1", "street-2", "landscape", "video-1", "video-2", "map"]

# ── Tier-aware config ──────────────────────────────────────────────────────
# (max_videos, max_gifs, sample_percents)
TIER_CONFIG = {
    1: {
        "max_videos": 4,
        "max_gifs": 5,
        "sample_percents": [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90],
    },
    2: {
        "max_videos": 3,
        "max_gifs": 3,
        "sample_percents": [0.12, 0.25, 0.40, 0.55, 0.70, 0.85],
    },
}
DEFAULT_TIER_CONFIG = {
    "max_videos": 2,
    "max_gifs": 1,
    "sample_percents": [0.15, 0.30, 0.50, 0.70, 0.85],
}


def get_tier_config(tier: int) -> dict:
    """Return extraction config for a given tier."""
    return TIER_CONFIG.get(tier, DEFAULT_TIER_CONFIG)


# ── Duration Parsing ──────────────────────────────────────────────────────
def parse_duration_seconds(duration_string: str) -> int:
    """Parse YouTube duration string to seconds.

    Formats: "34:12" (MM:SS), "1:34:12" (H:MM:SS), "2:34" (M:SS), "54" (SS).
    Returns 0 on failure.
    """
    if not duration_string or not isinstance(duration_string, str):
        return 0
    parts = duration_string.strip().split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(nums) == 1:
        return nums[0]  # bare seconds, e.g. "54"
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return 0


# ── Video Selection ───────────────────────────────────────────────────────
def select_videos(race_data: dict, max_videos: int = 2) -> list[dict]:
    """Top videos: curated first, then by view count.
    Filter: 3min <= duration <= 2hr (skip trailers and livestreams)."""
    yt = race_data.get("youtube_data", {})
    videos = yt.get("videos", [])
    if not videos:
        return []

    eligible = []
    for v in videos:
        dur = parse_duration_seconds(v.get("duration_string", ""))
        if MIN_DURATION_SEC <= dur <= MAX_DURATION_SEC:
            eligible.append(v)

    # Sort: curated first, then by view count descending
    eligible.sort(key=lambda v: (not v.get("curated", False), -(v.get("view_count", 0) or 0)))
    return eligible[:max_videos]


# ── Timestamp Computation ─────────────────────────────────────────────────
def compute_timestamps(videos: list[dict],
                       sample_percents: list[float] | None = None) -> list[dict]:
    """Compute sample timestamps for each video.

    Returns list of dicts: {video_id, channel, timestamp, video_index}.
    """
    if sample_percents is None:
        sample_percents = DEFAULT_TIER_CONFIG["sample_percents"]

    results = []
    for vi, v in enumerate(videos):
        dur = parse_duration_seconds(v.get("duration_string", ""))
        if dur <= 0:
            continue
        vid = v.get("video_id", "")
        channel = v.get("channel", "")
        for pct in sample_percents:
            t = int(dur * pct)
            results.append({
                "video_id": vid,
                "channel": channel,
                "timestamp": t,
                "video_index": vi,
            })
    return results


# ── Download & Extract ────────────────────────────────────────────────────
def download_segment(video_id: str, timestamp: int, tmp_dir: str,
                     height: int = 720) -> str | None:
    """Download a 3-second segment using yt-dlp. Returns path or None."""
    t_end = timestamp + CLIP_SECONDS
    out_template = os.path.join(tmp_dir, f"{video_id}_{timestamp}.%(ext)s")
    cmd = [
        "yt-dlp",
        f"https://www.youtube.com/watch?v={video_id}",
        "--download-sections", f"*{timestamp}-{t_end}",
        "-f", f"bestvideo[height<={height}]/best[height<={height}]",
        "--no-audio",
        "-o", out_template,
        "--no-warnings",
        "--quiet",
    ]
    try:
        subprocess.run(cmd, timeout=SUBPROCESS_TIMEOUT, check=True,
                       capture_output=True, text=True)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        _log(f"    yt-dlp failed for {video_id}@{timestamp}s: {e}")
        return None

    # Find the downloaded file (extension varies)
    for f in Path(tmp_dir).glob(f"{video_id}_{timestamp}.*"):
        if f.suffix in (".mp4", ".webm", ".mkv"):
            return str(f)
    return None


def extract_frame(segment_path: str, output_path: str) -> bool:
    """Extract one frame from a video segment using ffmpeg. Returns success."""
    cmd = [
        "ffmpeg", "-y", "-i", segment_path,
        "-vframes", "1", "-q:v", "2", output_path,
    ]
    try:
        subprocess.run(cmd, timeout=30, check=True, capture_output=True, text=True)
        return Path(output_path).exists()
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False


def extract_multiple_frames(segment_path: str, tmp_dir: str,
                            prefix: str, count: int = 5) -> list[str]:
    """Extract multiple evenly-spaced frames from a segment for motion scoring.
    Returns list of frame paths."""
    paths = []
    for i in range(count):
        # Seek to i/(count-1) through the clip (or just start for count=1)
        seek = (i * CLIP_SECONDS / max(count - 1, 1))
        out_path = os.path.join(tmp_dir, f"{prefix}_mf{i}.jpg")
        cmd = [
            "ffmpeg", "-y", "-ss", f"{seek:.2f}", "-i", segment_path,
            "-vframes", "1", "-q:v", "2", out_path,
        ]
        try:
            subprocess.run(cmd, timeout=15, check=True, capture_output=True, text=True)
            if Path(out_path).exists():
                paths.append(out_path)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            continue
    return paths


# ── Frame Quality Scoring (Pillow only) ───────────────────────────────────
def is_black_frame(img: Image.Image, threshold: float = 15.0) -> bool:
    """Reject frames with mean brightness < threshold."""
    stat = ImageStat.Stat(img.convert("L"))
    return stat.mean[0] < threshold


def has_text_overlay(img: Image.Image, edge_threshold: float = 40.0) -> bool:
    """Detect title cards, sponsor logos, and ad overlays.

    Checks:
    1. Top/bottom 25% strips — catches title cards, subscribe bars
    2. Bright text clusters — catches white sponsor text on scenery
    """
    w, h = img.size
    strip_h = int(h * 0.25)

    # Top and bottom strips (lower threshold — common for title cards)
    for region in [img.crop((0, 0, w, strip_h)), img.crop((0, h - strip_h, w, h))]:
        gray = region.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        stat = ImageStat.Stat(edges)
        if stat.mean[0] > edge_threshold:
            return True

    # Bright text detection: look for large clusters of near-white pixels
    # against a non-white background (sponsor overlays are typically white text)
    if _has_bright_text_clusters(img):
        return True

    return False


def _has_bright_text_clusters(img: Image.Image, bright_threshold: int = 230,
                              min_bright_pct: float = 0.03,
                              max_bright_pct: float = 0.30) -> bool:
    """Detect bright text overlays (white/near-white text on darker background).

    Returns True if the frame has a suspicious amount of very bright pixels
    clustered in a pattern consistent with text overlays:
    - 3-30% of pixels are near-white (text is large but not the whole frame)
    - The surrounding area is significantly darker (it's overlay, not sky)
    """
    gray = img.convert("L")
    pixels = list(gray.getdata())
    total = len(pixels)

    bright_count = sum(1 for p in pixels if p >= bright_threshold)
    bright_pct = bright_count / total

    # Must have some bright pixels but not too many (all-sky would be ~60%+)
    if not (min_bright_pct <= bright_pct <= max_bright_pct):
        return False

    # Check that non-bright pixels are significantly darker (confirms overlay vs sky)
    dark_pixels = [p for p in pixels if p < bright_threshold]
    if not dark_pixels:
        return False
    dark_mean = sum(dark_pixels) / len(dark_pixels)

    # Bright text on darker scenery: big gap between text brightness and background
    if (bright_threshold - dark_mean) > 100:
        # Additional check: bright pixels should have sharp edges nearby
        # (text has defined edges, clouds don't)
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_stat = ImageStat.Stat(edges)
        if edge_stat.mean[0] > 25:
            return True

    return False


def score_brightness(img: Image.Image) -> float:
    """Score 0-1: penalize too dark (<30 mean) or blown out (>240)."""
    stat = ImageStat.Stat(img.convert("L"))
    mean = stat.mean[0]
    if mean < 30:
        return mean / 30.0 * 0.3
    if mean > 240:
        return (255 - mean) / 15.0 * 0.3
    # Ideal: 80-180
    if 80 <= mean <= 180:
        return 1.0
    if mean < 80:
        return 0.3 + 0.7 * (mean - 30) / 50.0
    return 0.3 + 0.7 * (240 - mean) / 60.0


def score_contrast(img: Image.Image) -> float:
    """Score 0-1: higher standard deviation = more contrast = better."""
    stat = ImageStat.Stat(img.convert("L"))
    std = stat.stddev[0]
    # Typical range 20-80; normalize to 0-1
    return min(std / 60.0, 1.0)


def score_sharpness(img: Image.Image) -> float:
    """Score 0-1: Laplacian variance — higher = sharper."""
    gray = img.convert("L")
    laplacian = gray.filter(ImageFilter.Kernel(
        size=(3, 3),
        kernel=[-1, -1, -1, -1, 8, -1, -1, -1, -1],
        scale=1, offset=0,
    ))
    stat = ImageStat.Stat(laplacian)
    variance = stat.var[0]
    # Typical range: blurry ~100, sharp ~2000+
    return min(variance / 1500.0, 1.0)


def score_nature_color(img: Image.Image) -> float:
    """Score 0-1: prefer green/brown (vegetation, dirt) over blue/gray."""
    rgb = img.convert("RGB")
    stat = ImageStat.Stat(rgb)
    r, g, b = stat.mean

    score = 0.0
    # Green vegetation: g > r and g > b
    if g > r and g > b:
        score += 0.5
    # Brown/earth: r > b, moderate values
    if r > b and 60 < r < 200:
        score += 0.3
    # Penalize heavy blue (sky-only frames)
    if b > r and b > g:
        score -= 0.2
    # Penalize gray/low saturation
    spread = max(r, g, b) - min(r, g, b)
    if spread < 20:
        score -= 0.3

    return max(0.0, min(1.0, score + 0.3))


def score_composition(img: Image.Image) -> float:
    """Score 0-1: penalize mostly-sky or mostly-ground frames."""
    w, h = img.size
    top_third = img.crop((0, 0, w, h // 3)).convert("L")
    bottom_third = img.crop((0, 2 * h // 3, w, h)).convert("L")

    top_mean = ImageStat.Stat(top_third).mean[0]
    bottom_mean = ImageStat.Stat(bottom_third).mean[0]

    score = 1.0
    # Heavy sky: top much brighter than bottom
    if top_mean > 200 and bottom_mean < 100:
        score -= 0.4
    # Mostly ground: bottom dark, top also dark
    if top_mean < 60 and bottom_mean < 60:
        score -= 0.3
    # Uniform: top ≈ bottom (no horizon interest)
    if abs(top_mean - bottom_mean) < 10:
        score -= 0.2

    return max(0.0, score)


def score_frame(img: Image.Image) -> float:
    """Composite quality score 0-100 from weighted heuristics."""
    return (
        score_brightness(img) * 20 +
        score_contrast(img) * 20 +
        score_sharpness(img) * 25 +
        score_nature_color(img) * 20 +
        score_composition(img) * 15
    )


# ── Motion Scoring (for GIF segment selection) ───────────────────────────
def score_motion(frame_paths: list[str]) -> float:
    """Score 0-1: how much motion/action a clip segment contains.

    Compares consecutive frames pixel-by-pixel. More difference = more action.
    High motion = mud splashing, tight corners, pack riding, terrain changes.
    """
    if len(frame_paths) < 2:
        return 0.0

    diffs = []
    prev = None
    for path in frame_paths:
        try:
            img = Image.open(path).convert("L").resize((160, 90))
        except Exception:
            continue
        if prev is not None:
            # Mean absolute pixel difference between consecutive frames
            prev_data = list(prev.getdata())
            curr_data = list(img.getdata())
            diff = sum(abs(a - b) for a, b in zip(prev_data, curr_data)) / len(prev_data)
            diffs.append(diff)
        prev = img

    if not diffs:
        return 0.0

    avg_diff = sum(diffs) / len(diffs)
    # Typical range: static=0-2, gentle pan=5-15, action=15-40+
    return min(avg_diff / 25.0, 1.0)


# ── Frame Diversity Selection ─────────────────────────────────────────────
def _frame_similarity(a: Image.Image, b: Image.Image) -> float:
    """Simple similarity: compare mean brightness + color channels.
    Returns value 0-1 where 1 = identical."""
    sa = ImageStat.Stat(a.convert("RGB"))
    sb = ImageStat.Stat(b.convert("RGB"))

    # Compare means of R, G, B, and luminance
    diff = sum(abs(ma - mb) for ma, mb in zip(sa.mean, sb.mean))
    # Max diff across 3 channels: 3 * 255 = 765
    return 1.0 - min(diff / 300.0, 1.0)


def select_best_frames(candidates: list[dict], max_frames: int = 3) -> list[dict]:
    """Top frames with diversity constraints.

    Each candidate: {path, score, video_index, img, ...}
    Constraints:
    - Max 2 from same video (visual diversity)
    - Skip near-duplicates (similarity > 0.9)
    """
    sorted_candidates = sorted(candidates, key=lambda c: -c["score"])
    selected = []
    video_counts: dict[int, int] = {}

    for c in sorted_candidates:
        if len(selected) >= max_frames:
            break

        vi = c["video_index"]
        # Max 2 per video
        if video_counts.get(vi, 0) >= 2:
            continue

        # Dedup similar frames
        is_dup = False
        for s in selected:
            if _frame_similarity(c["img"], s["img"]) > 0.9:
                is_dup = True
                break
        if is_dup:
            continue

        selected.append(c)
        video_counts[vi] = video_counts.get(vi, 0) + 1

    return selected


def select_best_gif_segments(candidates: list[dict], max_gifs: int = 1) -> list[dict]:
    """Select diverse GIF segments prioritizing motion/action.

    Each candidate: {video_id, timestamp, video_index, channel, motion_score,
                     frame_score, img}
    Selection:
    - Rank by combined score (motion * 0.6 + frame quality * 0.4)
    - Spread across different videos (max 2 per video for T1, unlimited for T3-4)
    - Skip near-duplicate timestamps (within 30s of each other on same video)
    """
    # Combined score: prefer action-heavy segments that also look good
    for c in candidates:
        c["combined_score"] = c["motion_score"] * 0.6 + c["frame_score"] * 0.4

    sorted_candidates = sorted(candidates, key=lambda c: -c["combined_score"])
    selected = []
    video_counts: dict[int, int] = {}
    max_per_video = max(2, max_gifs)  # allow up to max_gifs from one video if needed

    for c in sorted_candidates:
        if len(selected) >= max_gifs:
            break

        vi = c["video_index"]
        if video_counts.get(vi, 0) >= max_per_video:
            continue

        # Skip timestamps within 30s of already-selected on same video
        too_close = False
        for s in selected:
            if s["video_id"] == c["video_id"]:
                if abs(s["timestamp"] - c["timestamp"]) < 30:
                    too_close = True
                    break
        if too_close:
            continue

        # Dedup visually similar segments
        is_dup = False
        for s in selected:
            if s.get("img") and c.get("img"):
                if _frame_similarity(c["img"], s["img"]) > 0.85:
                    is_dup = True
                    break
        if is_dup:
            continue

        selected.append(c)
        video_counts[vi] = video_counts.get(vi, 0) + 1

    return selected


# ── Photo Output ──────────────────────────────────────────────────────────
def save_photo(img: Image.Image, output_path: str) -> bool:
    """Resize and save as JPEG at target dimensions."""
    resized = img.resize((PHOTO_WIDTH, PHOTO_HEIGHT), Image.LANCZOS)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    resized.save(output_path, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return Path(output_path).exists()


def generate_gif(video_id: str, timestamp: int, slug: str, tmp_dir: str,
                 gif_index: int = 0) -> str | None:
    """Generate optimized preview GIF. Returns output path or None.

    gif_index: 0 = "preview.gif", 1+ = "preview-2.gif", etc.
    """
    t_end = timestamp + CLIP_SECONDS
    out_template = os.path.join(tmp_dir, f"{video_id}_{timestamp}_gif{gif_index}.%(ext)s")

    # Download at lower res for smaller GIF
    cmd_dl = [
        "yt-dlp",
        f"https://www.youtube.com/watch?v={video_id}",
        "--download-sections", f"*{timestamp}-{t_end}",
        "-f", "bestvideo[height<=480]/best[height<=480]",
        "--no-audio",
        "-o", out_template,
        "--no-warnings", "--quiet",
    ]
    try:
        subprocess.run(cmd_dl, timeout=SUBPROCESS_TIMEOUT, check=True,
                       capture_output=True, text=True)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        _log(f"    GIF download failed: {e}")
        return None

    # Find downloaded file
    dl_path = None
    for f in Path(tmp_dir).glob(f"{video_id}_{timestamp}_gif{gif_index}.*"):
        if f.suffix in (".mp4", ".webm", ".mkv"):
            dl_path = str(f)
            break
    if not dl_path:
        return None

    slug_dir = PHOTOS_DIR / slug
    slug_dir.mkdir(parents=True, exist_ok=True)

    suffix = "" if gif_index == 0 else f"-{gif_index + 1}"
    output_gif = str(slug_dir / f"{slug}-preview{suffix}.gif")
    palette_path = os.path.join(tmp_dir, f"palette{gif_index}.png")

    # Generate palette (128 colors for smaller file size)
    cmd_palette = [
        "ffmpeg", "-y", "-i", dl_path,
        "-vf", f"fps={GIF_FPS},scale={GIF_WIDTH}:-1:flags=lanczos,palettegen=max_colors=128",
        palette_path,
    ]
    # Render GIF with palette + bayer dither for smaller size
    cmd_gif = [
        "ffmpeg", "-y", "-i", dl_path, "-i", palette_path,
        "-lavfi", f"fps={GIF_FPS},scale={GIF_WIDTH}:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
        output_gif,
    ]
    try:
        subprocess.run(cmd_palette, timeout=30, check=True, capture_output=True, text=True)
        subprocess.run(cmd_gif, timeout=30, check=True, capture_output=True, text=True)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        _log(f"    GIF render failed: {e}")
        return None

    if Path(output_gif).exists():
        size_kb = Path(output_gif).stat().st_size / 1024
        _log(f"    GIF #{gif_index + 1}: {size_kb:.0f}KB")
        return output_gif
    return None


# ── Photo Schema ──────────────────────────────────────────────────────────
def build_photo_entries(slug: str, photo_paths: list[str],
                        gif_paths: list[str],
                        channels: list[str],
                        photo_scores: list[float] = None) -> list[dict]:
    """Build photo entries matching the v2 schema."""
    credit = f"YouTube / {channels[0]}" if channels else "YouTube"
    display_name = slug.replace("-", " ").title()
    entries = []

    for i, path in enumerate(photo_paths):
        ptype = f"video-{i + 1}"
        fname = f"{slug}-{ptype}.jpg"
        entry = {
            "type": ptype,
            "file": fname,
            "url": f"/race-photos/{slug}/{fname}",
            "alt": f"Course scenery from {display_name} race footage",
            "credit": credit,
            "primary": i == 0,
        }
        if photo_scores and i < len(photo_scores):
            entry["quality_score"] = round(photo_scores[i], 1)
        entries.append(entry)

    for i, gif_path in enumerate(gif_paths):
        suffix = "" if i == 0 else f"-{i + 1}"
        gif_fname = f"{slug}-preview{suffix}.gif"
        entries.append({
            "type": "preview-gif",
            "file": gif_fname,
            "url": f"/race-photos/{slug}/{gif_fname}",
            "alt": f"Course preview from {display_name} race footage",
            "credit": credit,
            "gif": True,
        })

    return entries


def merge_photos(existing: list[dict], new_entries: list[dict]) -> list[dict]:
    """Merge new video photos into existing photos list.

    - Replaces existing video-* and preview-gif entries
    - Preserves street-*, landscape, map entries from v2 pipeline
    """
    # Remove old video-* and preview-gif entries
    kept = [p for p in existing
            if not p.get("type", "").startswith("video-")
            and p.get("type") != "preview-gif"]
    # Ensure primary is correct: new video-1 is primary only if no street/landscape exists
    has_higher_priority = any(
        p.get("type") in {"street-1", "street-2", "landscape"}
        for p in kept
    )
    if has_higher_priority:
        for e in new_entries:
            e["primary"] = False

    return kept + new_entries


# ── Race JSON Update ──────────────────────────────────────────────────────
def update_race_json(slug: str, photo_entries: list[dict]) -> bool:
    """Write photo entries into race JSON. Returns success."""
    json_path = DATA_DIR / f"{slug}.json"
    if not json_path.exists():
        _log(f"    ERROR: {json_path} not found")
        return False
    try:
        data = json.loads(json_path.read_text())
    except json.JSONDecodeError as e:
        _log(f"    ERROR: JSON parse failed: {e}")
        return False

    race = data.get("race", data)
    existing = race.get("photos", [])
    race["photos"] = merge_photos(existing, photo_entries)

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return True


# ── Progress Tracking ─────────────────────────────────────────────────────
def load_progress() -> dict:
    """Load progress from _progress.json."""
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_progress(progress: dict):
    """Save progress to _progress.json."""
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2) + "\n")


def _log(msg: str):
    """Print and append to log file."""
    print(msg)
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")


# ── Candidate Selection ──────────────────────────────────────────────────
def get_candidates(max_races: int, force: bool = False) -> list[dict]:
    """Get races eligible for screenshot extraction.

    Sorted by tier (ascending), then score (descending).
    Skips races that already have video photos unless --force.
    """
    progress = load_progress()
    candidates = []

    for json_file in sorted(DATA_DIR.glob("*.json")):
        try:
            data = json.loads(json_file.read_text())
        except json.JSONDecodeError:
            continue

        race = data.get("race", data)
        slug = race.get("slug", json_file.stem)
        yt = race.get("youtube_data", {})

        # Must have videos
        if not yt.get("videos"):
            continue

        # Skip if already done (unless --force)
        if not force and slug in progress:
            continue

        # Skip if already has video photos (unless --force)
        if not force:
            existing_photos = race.get("photos", [])
            if any(p.get("type", "").startswith("video-") for p in existing_photos):
                continue

        tier = race.get("gravel_god_rating", {}).get("tier", 4)
        score = race.get("gravel_god_rating", {}).get("overall_score", 0)
        candidates.append({
            "slug": slug,
            "tier": tier,
            "score": score,
            "data": data,
        })

    # Sort: T1 first, then highest score
    candidates.sort(key=lambda c: (c["tier"], -c["score"]))
    return candidates[:max_races]


# ── Main Pipeline ─────────────────────────────────────────────────────────
def extract_screenshots(slug: str, data: dict, dry_run: bool = False,
                        max_frames: int = 3, no_gif: bool = False) -> bool:
    """Full extraction pipeline for a single race. Returns success."""
    race = data.get("race", data)
    tier = race.get("gravel_god_rating", {}).get("tier", 4)
    tc = get_tier_config(tier)
    _log(f"\n  Extracting screenshots: {slug} (T{tier})")

    # 1. Select videos (tier-aware count)
    videos = select_videos(race, max_videos=tc["max_videos"])
    if not videos:
        _log(f"    SKIP: no eligible videos")
        return False

    _log(f"    Videos: {len(videos)} selected")
    for v in videos:
        _log(f"      - {v.get('channel')}: {v.get('title', '')[:50]}... "
             f"({v.get('duration_string')}, {v.get('view_count', 0):,} views)")

    # 2. Compute timestamps (tier-aware density)
    timestamps = compute_timestamps(videos, sample_percents=tc["sample_percents"])
    _log(f"    Timestamps: {len(timestamps)} sample points")

    max_gifs = 0 if no_gif else tc["max_gifs"]

    if dry_run:
        _log(f"    [DRY RUN] Would download {len(timestamps)} segments, "
             f"extract {max_frames} photos + up to {max_gifs} GIFs")
        return True

    # 3-5. Download, extract, score
    candidates = []
    gif_candidates = []

    with tempfile.TemporaryDirectory(prefix="gg_screenshots_") as tmp_dir:
        for ts in timestamps:
            vid = ts["video_id"]
            t = ts["timestamp"]

            # Download segment
            seg_path = download_segment(vid, t, tmp_dir)
            if not seg_path:
                continue

            # Extract frame
            frame_path = os.path.join(tmp_dir, f"{vid}_{t}.jpg")
            if not extract_frame(seg_path, frame_path):
                continue

            # Load and score
            try:
                img = Image.open(frame_path)
            except Exception:
                continue

            # Hard rejection filters
            if is_black_frame(img):
                continue
            if has_text_overlay(img):
                continue

            frame_score = score_frame(img)
            candidates.append({
                "path": frame_path,
                "score": frame_score,
                "video_id": vid,
                "video_index": ts["video_index"],
                "channel": ts["channel"],
                "timestamp": t,
                "img": img,
            })

            # Score motion for GIF selection (T1-T2 get multi-GIF)
            if max_gifs > 0:
                motion_frames = extract_multiple_frames(
                    seg_path, tmp_dir, f"{vid}_{t}", count=5)
                motion = score_motion(motion_frames) if motion_frames else 0.0
                gif_candidates.append({
                    "video_id": vid,
                    "timestamp": t,
                    "video_index": ts["video_index"],
                    "channel": ts["channel"],
                    "motion_score": motion,
                    "frame_score": frame_score / 100.0,  # normalize to 0-1
                    "img": img,
                    "seg_path": seg_path,
                })

        _log(f"    Candidates: {len(candidates)} passed quality filters")

        if not candidates:
            _log(f"    SKIP: no quality frames found")
            return False

        # 6. Select best frames for stills
        best = select_best_frames(candidates, max_frames)
        _log(f"    Selected: {len(best)} frames (scores: "
             f"{', '.join(f'{b['score']:.1f}' for b in best)})")

        # 7. Save photos
        slug_dir = PHOTOS_DIR / slug
        slug_dir.mkdir(parents=True, exist_ok=True)

        photo_paths = []
        for i, b in enumerate(best):
            fname = f"{slug}-video-{i + 1}.jpg"
            out_path = str(slug_dir / fname)
            if save_photo(b["img"], out_path):
                photo_paths.append(out_path)
                size_kb = Path(out_path).stat().st_size / 1024
                _log(f"    Saved: {fname} ({size_kb:.0f}KB, score={b['score']:.1f})")

        # 8. Generate GIFs (tier-aware count)
        gif_paths = []
        if max_gifs > 0 and gif_candidates:
            best_gifs = select_best_gif_segments(gif_candidates, max_gifs)
            _log(f"    GIF segments: {len(best_gifs)} selected "
                 f"(motion: {', '.join(f'{g['motion_score']:.2f}' for g in best_gifs)})")

            for gi, g in enumerate(best_gifs):
                gp = generate_gif(g["video_id"], g["timestamp"], slug, tmp_dir,
                                  gif_index=gi)
                if gp:
                    gif_paths.append(gp)

    # 9. Update race JSON
    channels = list(dict.fromkeys(b["channel"] for b in best))  # ordered unique
    photo_scores = [b["score"] for b in best]
    entries = build_photo_entries(slug, photo_paths, gif_paths, channels,
                                 photo_scores=photo_scores)
    if entries:
        update_race_json(slug, entries)
        _log(f"    Updated: {slug}.json with {len(entries)} photo entries")

    # 10. Update progress
    progress = load_progress()
    avg_score = round(sum(photo_scores) / len(photo_scores), 1) if photo_scores else 0
    progress[slug] = {
        "extracted_at": date.today().isoformat(),
        "photos": len(photo_paths),
        "gifs": len(gif_paths),
        "avg_score": avg_score,
    }
    save_progress(progress)

    _log(f"  SUCCESS: {slug} — {len(photo_paths)} photos + {len(gif_paths)} GIFs")
    return True


# ── Status Report ─────────────────────────────────────────────────────────
def print_status():
    """Print coverage report."""
    progress = load_progress()
    total_with_yt = 0
    total_extracted = 0
    total_photos = 0
    total_gifs = 0

    for json_file in sorted(DATA_DIR.glob("*.json")):
        try:
            data = json.loads(json_file.read_text())
        except json.JSONDecodeError:
            continue

        race = data.get("race", data)
        slug = race.get("slug", json_file.stem)
        yt = race.get("youtube_data", {})

        if yt.get("videos"):
            total_with_yt += 1

        if slug in progress:
            total_extracted += 1
            total_photos += progress[slug].get("photos", 0)
            total_gifs += progress[slug].get("gifs", progress[slug].get("gif", 0))
            if isinstance(total_gifs, bool):
                total_gifs = 1 if total_gifs else 0

    print(f"\n{'=' * 50}")
    print(f"YouTube Screenshots Status")
    print(f"{'=' * 50}")
    print(f"Races with YouTube videos: {total_with_yt}")
    print(f"Races extracted:           {total_extracted}")
    print(f"Remaining:                 {total_with_yt - total_extracted}")
    print(f"Total photos:              {total_photos}")
    print(f"Total GIFs:                {total_gifs}")
    print(f"{'=' * 50}")


# ── CLI ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Extract screenshots and preview GIFs from YouTube race videos.")
    parser.add_argument("--slug", nargs="+", help="Race slug(s) to extract")
    parser.add_argument("--auto", type=int, metavar="N",
                        help="Auto-extract top N priority races")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without downloading")
    parser.add_argument("--force", action="store_true",
                        help="Re-extract even if screenshots exist")
    parser.add_argument("--delay", type=int, default=5,
                        help="Seconds between races (default: 5)")
    parser.add_argument("--max-frames", type=int, default=3,
                        help="Max photo frames per race (default: 3)")
    parser.add_argument("--no-gif", action="store_true",
                        help="Skip GIF generation")
    parser.add_argument("--status", action="store_true",
                        help="Print coverage report and exit")
    args = parser.parse_args()

    if args.status:
        print_status()
        return 0

    if not args.slug and args.auto is None:
        parser.error("Provide --slug or --auto N (or --status)")

    # Verify tools (unless dry-run)
    if not args.dry_run:
        for tool, flag in [("yt-dlp", "--version"), ("ffmpeg", "-version")]:
            try:
                subprocess.run([tool, flag], capture_output=True, check=True)
            except FileNotFoundError:
                sys.exit(f"ERROR: {tool} not found. Install it first.")

    # Build work list
    if args.slug:
        slugs_to_do = []
        for slug in args.slug:
            json_path = DATA_DIR / f"{slug}.json"
            if not json_path.exists():
                _log(f"  WARNING: {slug}.json not found, skipping")
                continue
            data = json.loads(json_path.read_text())
            slugs_to_do.append({"slug": slug, "data": data})
    else:
        candidates = get_candidates(args.auto, force=args.force)
        slugs_to_do = [{"slug": c["slug"], "data": c["data"]} for c in candidates]

    _log(f"\n{'=' * 50}")
    _log(f"YouTube Screenshots: {len(slugs_to_do)} races")
    _log(f"{'=' * 50}")

    success = 0
    failed = 0
    skipped = 0

    for i, item in enumerate(slugs_to_do):
        if i > 0 and not args.dry_run:
            time.sleep(args.delay)

        try:
            result = extract_screenshots(
                item["slug"], item["data"],
                dry_run=args.dry_run,
                max_frames=args.max_frames,
                no_gif=args.no_gif,
            )
            if result:
                success += 1
            else:
                skipped += 1
        except KeyboardInterrupt:
            _log("\n  Interrupted by user")
            break
        except Exception as e:
            _log(f"  ERROR: {item['slug']}: {e}")
            failed += 1

    _log(f"\n{'=' * 50}")
    _log(f"Done: {success} success, {skipped} skipped, {failed} failed")
    _log(f"{'=' * 50}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
