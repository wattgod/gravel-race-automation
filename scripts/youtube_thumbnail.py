#!/usr/bin/env python3
"""
youtube_thumbnail.py — Fetch, score, and cache YouTube thumbnails.

Standalone module that keeps PIL dependency isolated from youtube_enrich.py.
Tries maxresdefault.jpg (1280x720) first, falls back to hqdefault.jpg (480x360).

Scoring uses heuristics from youtube_screenshots.py (brightness, contrast,
nature color, black frame detection, text overlay detection).

Usage:
    from youtube_thumbnail import score_thumbnail, get_best_thumbnail_url

    result = score_thumbnail("dQw4w9WgXcQ")
    # {"score": 62.5, "has_text": False, "is_black": False, "has_maxres": True,
    #  "brightness": 0.85, "contrast": 0.7, "nature_color": 0.5}

    url = get_best_thumbnail_url("dQw4w9WgXcQ", has_maxres=True)
    # "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
"""

import time
import urllib.request
import urllib.error
from pathlib import Path

# PIL is optional — import errors handled by callers
from PIL import Image, ImageFilter, ImageStat

# ── Paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "data" / "thumbnail-cache"
CACHE_TTL_DAYS = 30

# ── Thumbnail URLs ───────────────────────────────────────────────────────
MAXRES_URL = "https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
HQDEFAULT_URL = "https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

# Placeholder thumbnails from YouTube are typically < 10KB
PLACEHOLDER_SIZE_BYTES = 10_000


def fetch_thumbnail(video_id: str) -> tuple[bytes, bool]:
    """Fetch thumbnail for a video. Returns (image_bytes, has_maxres).

    Tries maxresdefault.jpg first. Falls back to hqdefault.jpg if maxres
    returns 404 or is a placeholder (< 10KB).

    Caches to data/thumbnail-cache/{video_id}.jpg with 30-day TTL.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{video_id}.jpg"
    maxres_marker = CACHE_DIR / f"{video_id}.maxres"

    # Check cache (30-day TTL)
    if cache_path.exists():
        age_days = (time.time() - cache_path.stat().st_mtime) / 86400
        if age_days < CACHE_TTL_DAYS:
            return cache_path.read_bytes(), maxres_marker.exists()

    # Try maxresdefault first
    has_maxres = False
    img_bytes = _fetch_url(MAXRES_URL.format(video_id=video_id))

    if img_bytes and len(img_bytes) >= PLACEHOLDER_SIZE_BYTES:
        has_maxres = True
    else:
        # Fallback to hqdefault
        img_bytes = _fetch_url(HQDEFAULT_URL.format(video_id=video_id))

    if not img_bytes:
        return b"", False

    # Write cache
    cache_path.write_bytes(img_bytes)
    if has_maxres:
        maxres_marker.touch()
    elif maxres_marker.exists():
        maxres_marker.unlink()

    return img_bytes, has_maxres


def _fetch_url(url: str) -> bytes | None:
    """Fetch URL bytes. Returns None on error."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (GravelGod Thumbnail Scorer)"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        pass
    return None


def score_thumbnail(video_id: str) -> dict:
    """Score a YouTube thumbnail. Returns dict with quality metrics.

    Keys:
        score (float): Composite score 0-100. brightness*30 + contrast*30 + nature_color*40.
        has_text (bool): Text overlay detected.
        is_black (bool): Dark/black frame.
        has_maxres (bool): Maxres thumbnail available.
        brightness (float): Brightness score 0-1.
        contrast (float): Contrast score 0-1.
        nature_color (float): Nature/cycling color score 0-1.
    """
    img_bytes, has_maxres = fetch_thumbnail(video_id)

    if not img_bytes:
        return {
            "score": 0.0,
            "has_text": False,
            "is_black": True,
            "has_maxres": False,
            "brightness": 0.0,
            "contrast": 0.0,
            "nature_color": 0.0,
        }

    import io
    img = Image.open(io.BytesIO(img_bytes))

    is_black = _is_black_frame(img)
    has_text = _has_text_overlay(img)
    brightness = _score_brightness(img)
    contrast = _score_contrast(img)
    nature_color = _score_nature_color(img)

    # Composite: brightness*30 + contrast*30 + nature_color*40
    composite = brightness * 30 + contrast * 30 + nature_color * 40

    return {
        "score": round(composite, 2),
        "has_text": has_text,
        "is_black": is_black,
        "has_maxres": has_maxres,
        "brightness": round(brightness, 3),
        "contrast": round(contrast, 3),
        "nature_color": round(nature_color, 3),
    }


def get_best_thumbnail_url(video_id: str, has_maxres: bool) -> str:
    """Return the best thumbnail URL for a video.

    Uses maxresdefault.jpg (1280x720) if available, otherwise hqdefault.jpg (480x360).
    """
    if has_maxres:
        return MAXRES_URL.format(video_id=video_id)
    return HQDEFAULT_URL.format(video_id=video_id)


# ── Scoring Functions (adapted from youtube_screenshots.py) ──────────────

def _is_black_frame(img: Image.Image, threshold: float = 15.0) -> bool:
    """Reject frames with mean brightness < threshold."""
    stat = ImageStat.Stat(img.convert("L"))
    return stat.mean[0] < threshold


def _has_text_overlay(img: Image.Image, edge_threshold: float = 40.0) -> bool:
    """Detect title cards, sponsor logos, and ad overlays via edge density."""
    w, h = img.size
    strip_h = int(h * 0.25)

    for region in [img.crop((0, 0, w, strip_h)), img.crop((0, h - strip_h, w, h))]:
        gray = region.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        stat = ImageStat.Stat(edges)
        if stat.mean[0] > edge_threshold:
            return True
    return False


def _score_brightness(img: Image.Image) -> float:
    """Score 0-1: penalize too dark (<30 mean) or blown out (>240)."""
    stat = ImageStat.Stat(img.convert("L"))
    mean = stat.mean[0]
    if mean < 30:
        return mean / 30.0 * 0.3
    if mean > 240:
        return (255 - mean) / 15.0 * 0.3
    if 80 <= mean <= 180:
        return 1.0
    if mean < 80:
        return 0.3 + 0.7 * (mean - 30) / 50.0
    return 0.3 + 0.7 * (240 - mean) / 60.0


def _score_contrast(img: Image.Image) -> float:
    """Score 0-1: higher standard deviation = more contrast = better."""
    stat = ImageStat.Stat(img.convert("L"))
    std = stat.stddev[0]
    return min(std / 60.0, 1.0)


def _score_nature_color(img: Image.Image) -> float:
    """Score 0-1: prefer green/brown (vegetation, dirt) over blue/gray."""
    rgb = img.convert("RGB")
    stat = ImageStat.Stat(rgb)
    r, g, b = stat.mean

    score = 0.0
    if g > r and g > b:
        score += 0.5
    if r > b and 60 < r < 200:
        score += 0.3
    if b > r and b > g:
        score -= 0.2
    spread = max(r, g, b) - min(r, g, b)
    if spread < 20:
        score -= 0.3

    return max(0.0, min(1.0, score + 0.3))
