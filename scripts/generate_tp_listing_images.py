#!/usr/bin/env python3
"""
Generate TP-listing images (header + includes-grid) for TrainingPeaks plan
descriptions. Sibling of scripts/generate_og_images.py — same font-loading
and output patterns, but builds the two hosted images the TP Listing v3 spec
calls for:

  1. HEADER image — logo, race name, tier chip, score/RACE RATING, radar pair
     (Course Profile / Editorial), baked at fill-opacity .25 (the site ships
     the radar invisible and animates it in; the static image must not).
  2. INCLUDES image — 6 standard tiles + conditional module tiles (altitude,
     masters) appended inline, per plan class.

Normative spec: gravel-god-training-plans/specs/desc-qc/TP_LISTING_ENGINEERING.md
Visual prototype: gravel-god-brand/design-lab/direction-tp-listing.html
Radar geometry ported from: wordpress/generate_neo_brutalist.py::_radar_svg

Usage:
    python3 scripts/generate_tp_listing_images.py --slug big-sugar
    python3 scripts/generate_tp_listing_images.py --slug big-sugar --plan-class finisher
    python3 scripts/generate_tp_listing_images.py --all-p0
"""

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageChops
except ImportError:
    print("ERROR: Pillow required. Install with: pip install Pillow")
    sys.exit(1)


# ── Repo layout ─────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DATA_DIR = REPO_ROOT / "race-data"
OUTPUT_DIR = REPO_ROOT / "wordpress" / "output" / "tp"
DEFAULT_PLANS_DB = REPO_ROOT.parent / "gravel-god-training-plans" / "db" / "plans.json"

FONT_DIR = REPO_ROOT / "guide" / "fonts"
FONT_EDITORIAL = str(FONT_DIR / "SourceSerif4-Variable.ttf")
FONT_EDITORIAL_ITALIC = str(FONT_DIR / "SourceSerif4-Italic-Variable.ttf")
FONT_DATA = str(FONT_DIR / "SometypeMono-Regular.ttf")
FONT_DATA_BOLD = str(FONT_DIR / "SometypeMono-Bold.ttf")

GENERATOR_VERSION = "tp-listing-v1"

# Type floor: no meaningful (information-bearing) text under 32px at the
# 2x scale this generator renders at (= 16 CSS px effective at 620px column
# width). Pure micro-branding (the "GRAVEL GOD CYCLING" kicker) and thin
# rule dividers are exempt — see README note in report.
TYPE_FLOOR_PX = 32


class TPListingError(Exception):
    """Base error for TP listing image generation."""


class DataIntegrityError(TPListingError):
    """Raised when race data is internally inconsistent (partial subscores,
    missing required vitals) rather than cleanly absent (pending state)."""


class NameOverflowError(TPListingError):
    """Raised when a race name cannot be wrapped into 2 lines without
    silently dropping content."""


class ContrastError(TPListingError):
    """Raised when a text/background color pair fails the WCAG AA
    threshold appropriate to its rendered size."""


class TypeFloorError(TPListingError):
    """Raised when meaningful text is drawn below TYPE_FLOOR_PX."""


# ── Brand colors — from gravel-god-brand/tokens/tokens.json ────

PAPER = (245, 239, 230)        # #f5efe6 — warm paper ground
DARK_BROWN = (58, 46, 37)      # #3a2e25 — primary-dark / max-contrast ink
SEC_BROWN = (125, 105, 93)     # #7d695d — secondary brown / metadata
SAND = (237, 228, 216)         # #ede4d8
TAN_BORDER = (216, 203, 187)   # #d8cbbb — tile borders
TAN_RULE = (221, 210, 194)     # #ddd2c2 — hairline rules
GOLD = (183, 149, 11)          # #9a7e0a — accent gold (celebratory / chips)
GOLD_DEEP = (154, 126, 10)     # #9a7e0a — gold-deep (labels/borders on paper)
TEAL = (23, 128, 121)          # #178079 — course-profile radar accent
WHITE = (255, 255, 255)
GRID_LINE = (125, 105, 93)     # secondary brown, used at low opacity for rings
AXIS_LINE = (212, 197, 185)    # #d4c5b9 tan, radar spokes

COURSE_DIMS = ["logistics", "length", "technicality", "elevation", "climate", "altitude", "adventure"]
OPINION_DIMS = ["prestige", "race_quality", "experience", "community", "field_depth", "value", "expenses"]
ALL_DIMS = COURSE_DIMS + OPINION_DIMS

# Full labels (for alt text) vs. short in-image labels (for the type-floor
# vs. compact-radar tension — see report). Alt text always mirrors the full
# name; the baked image uses a 3-letter code sized to clear the 32px floor.
DIM_LABELS = {
    "logistics": "Logistics", "length": "Length", "technicality": "Technical",
    "elevation": "Elevation", "climate": "Climate", "altitude": "Altitude",
    "adventure": "Adventure", "prestige": "Prestige", "race_quality": "Quality",
    "experience": "Experience", "community": "Community", "field_depth": "Field",
    "value": "Value", "expenses": "Expenses",
}
DIM_SHORT = {
    "logistics": "LOG", "length": "LEN", "technicality": "TEC",
    "elevation": "ELV", "climate": "CLI", "altitude": "ALT",
    "adventure": "ADV", "prestige": "PRE", "race_quality": "QUA",
    "experience": "EXP", "community": "COM", "field_depth": "FLD",
    "value": "VAL", "expenses": "CST",
}

TIER_SLUG = {
    "Finisher": "finisher",
    "Compete": "compete",
    "Masters 50+": "masters",
    "Time-Crunched": "time-crunched",
    "Save My Race": "save-my-race",
}

P0_SLUGS = [
    "big-sugar", "bwr-montana", "gravel-locos", "pisgah-monster-cross",
    "unbound-100", "lauf-true-grit", "noosa-gravel-enduro", "d2r2",
]

ALTITUDE_THRESHOLD_FT = 5000


# ── Contrast (WCAG AA) ──────────────────────────────────────────

def _srgb_to_linear(c: int) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(rgb: tuple) -> float:
    r, g, b = rgb
    return 0.2126 * _srgb_to_linear(r) + 0.7152 * _srgb_to_linear(g) + 0.0722 * _srgb_to_linear(b)


def contrast_ratio(rgb1: tuple, rgb2: tuple) -> float:
    l1, l2 = _relative_luminance(rgb1), _relative_luminance(rgb2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def assert_contrast(fg: tuple, bg: tuple, px_size: int, bold: bool, context: str) -> float:
    """Assert the fg/bg pair clears WCAG AA for its rendered size.

    Large text (>=24px regular, or >=18.66px/~19px bold) only needs 3:1;
    everything else needs 4.5:1. Raises ContrastError (not a silent fudge)
    if the pair fails the threshold that applies at this size.
    """
    ratio = contrast_ratio(fg, bg)
    is_large = px_size >= 24 or (bold and px_size >= 19)
    threshold = 3.0 if is_large else 4.5
    if ratio < threshold:
        raise ContrastError(
            f"{context}: contrast {ratio:.2f}:1 fails AA threshold {threshold}:1 "
            f"(fg={fg} bg={bg} size={px_size} bold={bold})"
        )
    return ratio


def assert_type_floor(px_size: int, context: str, meaningful: bool = True) -> None:
    """Assert meaningful text clears the 32px (2x-scale) type floor."""
    if meaningful and px_size < TYPE_FLOOR_PX:
        raise TypeFloorError(
            f"{context}: {px_size}px is under the {TYPE_FLOOR_PX}px type floor"
        )


# ── Font loading (mirrors scripts/generate_og_images.py) ────────

_FONT_CACHE = {}


def load_font(path: str, size: int, weight: int = None) -> "ImageFont.FreeTypeFont":
    key = (path, size, weight)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    try:
        font = ImageFont.truetype(path, size)
        if weight is not None:
            try:
                font.set_variation_by_axes([weight])
            except Exception:
                pass
    except (OSError, IOError):
        font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


def tw(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def th(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def wrap_lines(draw, text, font, max_width, max_lines=2):
    """Deterministic greedy word wrap. Raises NameOverflowError if the text
    cannot fit within max_lines without dropping a word (no silent clipping).
    """
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if tw(draw, test, font) <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = word
        if len(lines) > max_lines:
            raise NameOverflowError(
                f"text does not fit in {max_lines} lines at this width: {text!r}"
            )
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        raise NameOverflowError(
            f"text does not fit in {max_lines} lines at this width: {text!r}"
        )
    return lines


# ── SVG path parsing + logo rasterization ────────────────────────
# Only M (absolute moveto), l (relative lineto), c (relative cubic bezier),
# z (closepath) appear in the canonical gg-logo path data — confirmed by
# inspection of gravel-god-brand/logo/gg-logo.min.svg. A full SVG path
# grammar is not needed.

_PATH_TOKEN_RE = re.compile(r"([MLCZmlcz])|(-?\d*\.?\d+(?:[eE]-?\d+)?)")

LOGO_SVG_CANDIDATES = [
    REPO_ROOT.parent / "gravel-god-brand" / "logo" / "gg-logo.min.svg",
    REPO_ROOT.parent / "gravel-god-brand" / "logo" / "gg-logo-2026.svg",
    REPO_ROOT / "gg-logo-2026.svg",
    REPO_ROOT / "web" / "gg-logo.svg",
]


def _flatten_cubic(p0, p1, p2, p3, n=10):
    pts = []
    for i in range(1, n + 1):
        t = i / n
        mt = 1 - t
        x = mt ** 3 * p0[0] + 3 * mt ** 2 * t * p1[0] + 3 * mt * t ** 2 * p2[0] + t ** 3 * p3[0]
        y = mt ** 3 * p0[1] + 3 * mt ** 2 * t * p1[1] + 3 * mt * t ** 2 * p2[1] + t ** 3 * p3[1]
        pts.append((x, y))
    return pts


def parse_svg_path_d(d: str) -> list:
    """Parse an SVG path 'd' string (M/l/c/z subset) into subpaths, each a
    flat list of (x, y) points in the path's local coordinate space."""
    tokens = []
    for m in _PATH_TOKEN_RE.finditer(d):
        if m.group(1):
            tokens.append(m.group(1))
        elif m.group(2):
            tokens.append(float(m.group(2)))

    subpaths = []
    cur = []
    pos = (0.0, 0.0)
    cmd = None
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if isinstance(t, str):
            cmd = t
            i += 1
            continue
        if cmd == "M":
            x, y = tokens[i], tokens[i + 1]
            i += 2
            pos = (x, y)
            if cur:
                subpaths.append(cur)
            cur = [pos]
        elif cmd == "l":
            dx, dy = tokens[i], tokens[i + 1]
            i += 2
            pos = (pos[0] + dx, pos[1] + dy)
            cur.append(pos)
        elif cmd == "c":
            dx1, dy1, dx2, dy2, dx, dy = tokens[i:i + 6]
            i += 6
            p1 = (pos[0] + dx1, pos[1] + dy1)
            p2 = (pos[0] + dx2, pos[1] + dy2)
            p3 = (pos[0] + dx, pos[1] + dy)
            cur.extend(_flatten_cubic(pos, p1, p2, p3))
            pos = p3
        elif cmd in ("z", "Z"):
            pass
        else:
            raise TPListingError(f"unsupported SVG path command {cmd!r} in logo asset")
    if cur:
        subpaths.append(cur)
    return subpaths


_LOGO_RASTER_CACHE = {}


def _find_logo_svg() -> Path:
    for candidate in LOGO_SVG_CANDIDATES:
        if candidate.exists():
            return candidate
    raise TPListingError(
        "no gg logo SVG asset found in any candidate location: "
        + ", ".join(str(c) for c in LOGO_SVG_CANDIDATES)
    )



# ── Browser-rasterized PNG assets (preferred over PIL redraws) ──────
# Rendered from the canonical SVGs (design-lab prototype + gg-logo.svg)
# via headless Chrome at 4x; committed under wordpress/assets/tp/.
# PIL drawing functions below remain as fallback when a PNG is absent.
ASSETS_TP_DIR = REPO_ROOT / "wordpress" / "assets" / "tp"
_PNG_ASSET_CACHE: dict = {}

def _png_asset(name: str, target_h: int) -> "Image.Image | None":
    key = (name, target_h)
    if key in _PNG_ASSET_CACHE:
        return _PNG_ASSET_CACHE[key]
    fp = ASSETS_TP_DIR / f"{name}.png"
    if not fp.exists():
        return None
    img = Image.open(fp).convert("RGBA")
    w = round(img.width * target_h / img.height)
    img = img.resize((w, target_h), Image.LANCZOS)
    _PNG_ASSET_CACHE[key] = img
    return img

def rasterize_logo(color: tuple, target_h: int) -> "Image.Image":
    """Rasterize the real gg logo SVG path to an RGBA silhouette of the
    given color and pixel height, using even-odd (XOR) fill so letterform
    counters render as holes rather than solid fill."""
    png = _png_asset("logo", target_h)
    if png is not None:
        return png
    cache_key = (color, target_h)
    if cache_key in _LOGO_RASTER_CACHE:
        return _LOGO_RASTER_CACHE[cache_key]

    svg_path = _find_logo_svg()
    content = svg_path.read_text()

    vb_match = re.search(r'viewBox="([\d.\s-]+)"', content)
    if not vb_match:
        raise TPListingError(f"logo SVG {svg_path} has no viewBox")
    _, _, view_w, view_h = (float(v) for v in vb_match.group(1).split())

    xf_match = re.search(
        r'transform="translate\(([\d.-]+),\s*([\d.-]+)\)\s*scale\(([\d.-]+),\s*([\d.-]+)\)"',
        content,
    )
    if xf_match:
        tx, ty, sx, sy = (float(v) for v in xf_match.groups())
    else:
        tx = ty = 0.0
        sx = sy = 1.0

    d_match = re.search(r'<path d="([^"]+)"', content)
    if not d_match:
        raise TPListingError(f"logo SVG {svg_path} has no <path d=...>")

    subpaths_raw = parse_svg_path_d(d_match.group(1))

    # Group transform is applied scale-then-translate (matrix composition
    # translate * scale applied to a point == translate(scale(point))).
    subpaths = [[(x * sx + tx, y * sy + ty) for x, y in sp] for sp in subpaths_raw]

    scale = target_h / view_h
    img_h = target_h
    img_w = max(1, round(view_w * scale))

    cumulative = Image.new("1", (img_w, img_h), 0)
    for sp in subpaths:
        if len(sp) < 3:
            continue
        pts = [(x * scale, y * scale) for x, y in sp]
        temp = Image.new("1", (img_w, img_h), 0)
        ImageDraw.Draw(temp).polygon(pts, fill=1)
        cumulative = ImageChops.logical_xor(cumulative, temp)

    solid = Image.new("RGBA", (img_w, img_h), color + (255,))
    transparent = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    result = Image.composite(solid, transparent, cumulative)
    _LOGO_RASTER_CACHE[cache_key] = result
    return result


# ── Race data loading ────────────────────────────────────────────

def load_race(slug: str, data_dir: Path = DATA_DIR) -> dict:
    path = data_dir / f"{slug}.json"
    if not path.exists():
        raise TPListingError(f"no race-data file for slug {slug!r}: {path}")
    with open(path) as f:
        raw = json.load(f)
    race = raw.get("race", raw)
    race.setdefault("slug", slug)
    return race


def rating_state(race: dict) -> str:
    """'rated' if a full, internally-consistent gravel_god_rating exists;
    'pending' if there's cleanly no rating yet. Raises DataIntegrityError
    for the in-between case (partial subscores) rather than zero-filling."""
    rating = race.get("gravel_god_rating") or race.get("rating") or {}
    overall = rating.get("overall_score")
    if overall is None:
        return "pending"
    have = [k for k in ALL_DIMS if rating.get(k) is not None]
    if len(have) == 0:
        return "pending"
    if len(have) < len(ALL_DIMS):
        missing = [k for k in ALL_DIMS if rating.get(k) is None]
        raise DataIntegrityError(
            f"{race.get('slug')}: overall_score present but subscores missing "
            f"for {missing} — never zero-fill, fix the source data"
        )
    return "rated"


def check_altitude_flag(race: dict) -> bool:
    vitals = race.get("vitals", {})
    start = vitals.get("start_elevation_asl_ft")
    avg = vitals.get("avg_elevation_asl_ft")
    for v in (start, avg):
        if isinstance(v, (int, float)) and v > ALTITUDE_THRESHOLD_FT:
            return True
    return False


# ── Plans DB / ladder ─────────────────────────────────────────────

def load_plans_db(path: Path = DEFAULT_PLANS_DB) -> list:
    if not path.exists():
        raise TPListingError(f"plans DB not found: {path}")
    with open(path) as f:
        data = json.load(f)
    return data["plans"]


def plans_for_race(all_plans: list, slug: str) -> list:
    return [p for p in all_plans if p.get("race_slug") == slug]


def plan_class_of(plan: dict) -> str:
    tier = plan.get("tier", "")
    return TIER_SLUG.get(tier, re.sub(r"[^a-z0-9]+", "-", tier.lower()).strip("-"))


def published_plans(race_plans: list) -> list:
    return [p for p in race_plans if p.get("status") == "published" and p.get("isPublic")]


def build_ladder(race_plans: list, self_plan: dict) -> list:
    """THIS PLAN row (unlinked) + published siblings only, self excluded from
    the sibling set. Suppressed entirely by the caller when empty."""
    rows = [{
        "title": self_plan.get("title", ""),
        "is_self": True,
        "marketplace_url": None,
    }]
    for p in published_plans(race_plans):
        if p.get("planId") == self_plan.get("planId"):
            continue
        rows.append({
            "title": p.get("title", ""),
            "is_self": False,
            "marketplace_url": p.get("marketplace_url"),
        })
    return rows


# ── Icon drawing (hand-redrawn in PIL to match the canonical set) ───
# Each icon is drawn into a square box [x, y, x+size, y+size]; icon_scale
# maps the canonical 24x24 viewBox coordinate space onto that box.

def _icon_scale(box):
    x0, y0, x1, y1 = box
    size = x1 - x0
    return lambda vx, vy: (x0 + vx / 24 * size, y0 + vy / 24 * size)


def draw_icon_calendar(draw, box):
    s = _icon_scale(box)
    lw = max(2, round((box[2] - box[0]) / 24 * 1.8))
    draw.rectangle([s(3, 5), s(21, 21)], outline=DARK_BROWN, width=lw)
    draw.line([s(3, 10), s(21, 10)], fill=DARK_BROWN, width=lw)
    draw.line([s(8, 3), s(8, 7)], fill=DARK_BROWN, width=lw)
    draw.line([s(16, 3), s(16, 7)], fill=DARK_BROWN, width=lw)
    draw.rectangle([s(6, 13), s(11, 17)], fill=GOLD)


def draw_icon_strength(draw, box):
    s = _icon_scale(box)
    lw = max(2, round((box[2] - box[0]) / 24 * 1.8))
    draw.rectangle([s(2, 9), s(6, 15)], fill=SAND, outline=DARK_BROWN, width=lw)
    draw.rectangle([s(18, 9), s(22, 15)], fill=SAND, outline=DARK_BROWN, width=lw)
    draw.line([s(6, 12), s(18, 12)], fill=DARK_BROWN, width=lw)


def draw_icon_flame(draw, box):
    s = _icon_scale(box)
    lw = max(2, round((box[2] - box[0]) / 24 * 1.6))
    p0, p1, p2, p3 = (12, 3), (9, 8), (5, 10), (5, 15)
    outer = _flatten_cubic(p0, p1, p2, p3, n=14)
    # approximate the "a7 7 0 0 0 14 0" bottom arc with a half-ellipse
    arc_pts = []
    for i in range(15):
        ang = math.pi * i / 14
        arc_pts.append((12 - 7 * math.cos(ang), 15 + 7 * math.sin(ang)))
    p4, p5, p6, p7 = (19, 15), (19, 10), (15, 8), (12, 3)
    inner = _flatten_cubic(p4, p5, p6, p7, n=14)
    poly = [p0] + outer + arc_pts + inner
    draw.polygon([s(*pt) for pt in poly], fill=SAND, outline=DARK_BROWN)
    tick = _flatten_cubic((12, 8), (10.5, 11), (9, 12), (9, 15), n=10)
    draw.line([s(*pt) for pt in [(12, 8)] + tick], fill=GOLD, width=lw)


def draw_icon_mountain(draw, box):
    s = _icon_scale(box)
    lw = max(2, round((box[2] - box[0]) / 24 * 1.6))
    draw.polygon([s(12, 3.5), s(21.5, 18.5), s(2.5, 18.5)], fill=SAND, outline=DARK_BROWN)
    draw.line([s(12, 4.5), s(9.5, 8.5), s(14.5, 8.5), s(10, 12.5), s(14.5, 12.5), s(10.5, 16.5)],
              fill=GOLD, width=lw)
    for cx in (6, 11, 16):
        cy = 21 if cx != 11 else 21.4
        r = 1.3
        draw.ellipse([s(cx - r, cy - r), s(cx + r, cy + r)], fill=DARK_BROWN)
        draw.line([s(cx, cy - 0.3), s(cx + 1.2, cy - 1.7)], fill=DARK_BROWN, width=max(1, lw - 1))


def draw_icon_head(draw, box):
    s = _icon_scale(box)
    lw = max(2, round((box[2] - box[0]) / 24 * 1.6))
    profile = _flatten_cubic((9, 21), (5.5, 16), (4.5, 12), (6.5, 9), n=12)
    profile += _flatten_cubic((6.5, 9), (9.6, 5.4), (16, 6.9), (19, 12.2), n=12)
    profile += _flatten_cubic((19, 12.2), (19, 14.4), (17.8, 15.6), (16.5, 16.8), n=12)
    poly = [(9, 21)] + profile + [(16.5, 21)]
    draw.polygon([s(*pt) for pt in poly], fill=SAND, outline=DARK_BROWN)
    draw.line([s(13.5, 8.5), s(10.5, 12.5), s(13.5, 12.5), s(11, 16)], fill=GOLD, width=lw)


def draw_icon_bottle(draw, box):
    s = _icon_scale(box)
    lw = max(2, round((box[2] - box[0]) / 24 * 1.8))
    draw.rectangle([s(10, 3), s(14, 5.6)], fill=DARK_BROWN)
    draw.line([s(12, 1), s(12, 3)], fill=DARK_BROWN, width=lw)
    body = [(9.4, 5.6), (14.6, 5.6), (15.5, 8.6), (15.5, 20.4), (8.5, 20.4), (8.5, 8.6)]
    draw.polygon([s(*pt) for pt in body], fill=WHITE, outline=DARK_BROWN, width=lw)
    droplet = _flatten_cubic((12, 11), (10.9, 13), (10.3, 14), (10.3, 15.2), n=10)
    droplet += _flatten_cubic((10.3, 15.2), (10.3, 16.14), (11.06, 16.9), (12, 16.9), n=10)
    droplet += _flatten_cubic((12, 16.9), (12.94, 16.9), (13.7, 16.14), (13.7, 15.2), n=10)
    droplet += _flatten_cubic((13.7, 15.2), (13.7, 14), (13.1, 13), (12, 11), n=10)
    draw.polygon([s(*pt) for pt in droplet], fill=GOLD)


def draw_icon_altitude(draw, box):
    """Conditional module: altitude gate (start/avg ASL > 5,000 ft)."""
    s = _icon_scale(box)
    lw = max(2, round((box[2] - box[0]) / 24 * 1.6))
    draw.polygon([s(4, 18), s(10, 8), s(13, 12.5), s(16, 7), s(21, 18)],
                 fill=SAND, outline=DARK_BROWN)
    draw.polygon([s(16, 7), s(14, 10.5), s(16.7, 10.5), s(15, 13), s(17.6, 13), s(16, 15)],
                  fill=GOLD)


def draw_icon_masters(draw, box):
    """Conditional module: Masters 50+ plan variant."""
    s = _icon_scale(box)
    lw = max(2, round((box[2] - box[0]) / 24 * 1.8))
    draw.ellipse([s(7, 3), s(17, 13)], outline=DARK_BROWN, width=lw)
    draw.line([s(12, 5.5), s(12, 8.2)], fill=GOLD, width=lw)
    draw.line([s(12, 8.2), s(14.4, 9.6)], fill=GOLD, width=lw)
    draw.arc([s(5, 12), s(19, 24)], start=200, end=340, fill=DARK_BROWN, width=lw)


ICON_DRAWERS = {
    "training": draw_icon_calendar,
    "strength": draw_icon_strength,
    "heat": draw_icon_flame,
    "skills": draw_icon_mountain,
    "mental": draw_icon_head,
    "fueling": draw_icon_bottle,
    "altitude": draw_icon_altitude,
    "masters": draw_icon_masters,
}

STANDARD_TILES = [
    ("training", "Structured rides tailored to your zones — exportable to your devices"),
    ("strength", "Strength built in, with video walkthroughs"),
    ("heat", "Heat-training protocols for racing in the hot stuff"),
    ("skills", "Workouts to improve your skills and ability in the peloton"),
    ("mental", "Weekly coach notes + the Gravel Grit mental program"),
    ("fueling", "How to optimize nutrition and hydration for training and racing"),
]

MODULE_TILES = {
    "altitude": ("altitude", "Altitude-adjusted pacing and acclimation guidance for this course's elevation"),
    "masters": ("masters", "Recovery-first structuring engineered for the Masters 50+ athlete"),
}


# ── Radar chart (ported from wordpress/generate_neo_brutalist.py::_radar_svg) ─

def _radar_point(cx, cy, r, angle_offset, n, i, dist):
    angle = angle_offset + i * 2 * math.pi / n
    return (cx + dist * math.cos(angle), cy + dist * math.sin(angle))


def draw_radar(base_img: "Image.Image", cx: int, cy: int, r: int, dims: list,
               scores: dict, color: tuple, label: str, font_axis, font_score,
               font_center, font_center_label, max_total: int):
    """Draw one radar (course or editorial) directly onto base_img (RGBA)."""
    draw = ImageDraw.Draw(base_img)
    n = len(dims)
    angle_offset = -math.pi / 2

    # Grid rings (1-5), faint.
    for level in range(1, 6):
        frac = level / 5
        pts = [_radar_point(cx, cy, r, angle_offset, n, i, r * frac) for i in range(n)]
        draw.polygon(pts, outline=GRID_LINE)

    # Axis spokes.
    for i in range(n):
        pt = _radar_point(cx, cy, r, angle_offset, n, i, r)
        draw.line([(cx, cy), pt], fill=AXIS_LINE, width=1)

    # Data polygon — baked at 25% opacity (site ships this invisible+
    # animated; static images must not ship at 0).
    scores_list = [scores[d] for d in dims]
    data_pts = [_radar_point(cx, cy, r, angle_offset, n, i, r * s / 5) for i, s in enumerate(scores_list)]
    overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).polygon(data_pts, fill=color + (64,))  # 64/255 ~= 25%
    composited = Image.alpha_composite(base_img.convert("RGBA"), overlay)
    base_img.paste(composited, (0, 0))
    draw = ImageDraw.Draw(base_img)
    draw.line(data_pts + [data_pts[0]], fill=color, width=3)

    # Score dots.
    for pt in data_pts:
        rad = 6
        draw.ellipse([pt[0] - rad, pt[1] - rad, pt[0] + rad, pt[1] + rad],
                     fill=color, outline=DARK_BROWN, width=2)

    # Axis labels (short code + n/5), positioned outside the ring.
    label_r = r + 46
    for i, dim in enumerate(dims):
        lx, ly = _radar_point(cx, cy, r, angle_offset, n, i, label_r)
        code = DIM_SHORT[dim]
        score_text = f"{scores[dim]}/5"
        assert_contrast(DARK_BROWN, PAPER, font_axis.size, True, f"radar axis label {code}")
        assert_contrast(color, PAPER, font_score.size, True, f"radar axis score {code}")
        assert_type_floor(font_axis.size, f"radar axis label {code}")
        assert_type_floor(font_score.size, f"radar axis score {code}")
        cw = tw(draw, code, font_axis)
        sw = tw(draw, score_text, font_score)
        draw.text((lx - cw / 2, ly - 26), code, fill=DARK_BROWN, font=font_axis)
        draw.text((lx - sw / 2, ly + 2), score_text, fill=color, font=font_score)

    # Center total.
    total = sum(scores_list)
    total_text = str(total)
    assert_type_floor(font_center.size, "radar center total")
    assert_contrast(color, PAPER, font_center.size, True, "radar center total")
    tw_ = tw(draw, total_text, font_center)
    draw.text((cx - tw_ / 2, cy - 22), total_text, fill=color, font=font_center)
    max_text = f"/{max_total}"
    assert_type_floor(font_center_label.size, "radar center max")
    mw = tw(draw, max_text, font_center_label)
    draw.text((cx - mw / 2, cy + 14), max_text, fill=SEC_BROWN, font=font_center_label)

    # Chart label underneath.
    assert_type_floor(font_center_label.size, "radar chart label")
    assert_contrast(DARK_BROWN, PAPER, font_center_label.size, True, "radar chart label")
    lbl_w = tw(draw, label, font_center_label)
    draw.text((cx - lbl_w / 2, cy + r + label_r - r + 6), label, fill=DARK_BROWN, font=font_center_label)


# ── Header image ─────────────────────────────────────────────────

HEADER_W = 1240


def _tier_label(race: dict) -> str:
    rating = race.get("gravel_god_rating") or race.get("rating") or {}
    return rating.get("tier_label") or f"TIER {rating.get('tier', '?')}"


def build_header_image(race: dict):
    """Returns (PIL.Image RGB, alt_text str)."""
    state = rating_state(race)
    name = race.get("display_name") or race.get("name") or race.get("slug")
    vitals = race.get("vitals", {})
    location = vitals.get("location", "")
    distance = f"{vitals.get('distance_mi')} MILES" if vitals.get("distance_mi") else ""
    date_specific = vitals.get("date_specific", "") or vitals.get("date", "")
    month_match = re.search(r"\b(January|February|March|April|May|June|July|August|"
                             r"September|October|November|December)\b", date_specific, re.I)
    month = month_match.group(1).upper() if month_match else ""

    margin = 48
    radar_h = 460 if state == "rated" else 0
    footer_pad = 40

    font_kicker = load_font(FONT_DATA_BOLD, 20)
    font_name = load_font(FONT_EDITORIAL, 56, weight=600)
    font_tier = load_font(FONT_DATA_BOLD, 32)
    font_meta = load_font(FONT_DATA, 32)
    font_score_big = load_font(FONT_DATA_BOLD, 76)
    font_score_slash = load_font(FONT_DATA, 32)
    font_score_label = load_font(FONT_DATA_BOLD, 32)
    font_axis = load_font(FONT_DATA_BOLD, 32)
    font_center = load_font(FONT_DATA_BOLD, 44)
    font_center_label = load_font(FONT_DATA_BOLD, 32)
    font_pending = load_font(FONT_EDITORIAL, 40, weight=600)

    # Logo.
    logo = rasterize_logo(DARK_BROWN, target_h=88)
    text_x = margin + logo.width + 20

    # Measurement pass — the top block's height depends on whether the race
    # name wraps to 1 or 2 lines, which we need to know before allocating
    # the real canvas (so the chip/meta row never overlaps a 2nd line).
    _measure_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    assert_type_floor(font_name.size, "race name")
    assert_contrast(DARK_BROWN, PAPER, font_name.size, True, "race name")
    name_max_w = HEADER_W - text_x - 380
    name_w = tw(_measure_draw, name, font_name)
    if name_w > name_max_w:
        # Long-name path: deterministic wrap, hard-error rather than clip.
        lines = wrap_lines(_measure_draw, name, font_name, name_max_w, max_lines=2)
    else:
        lines = [name]

    name_line_h = 62
    chip_y = 52 + len(lines) * name_line_h + 8
    th_chip = th(_measure_draw, "TIER", font_tier) + 16
    top_h = chip_y + th_chip + 20
    height = top_h + radar_h + footer_pad

    img = Image.new("RGBA", (HEADER_W, height), PAPER + (255,))
    draw = ImageDraw.Draw(img)
    img.paste(logo, (margin, 28), logo)

    # NOTE: the "GRAVEL GOD CYCLING" kicker is exempt from the type floor —
    # it is micro-branding, not information the rider needs to read (see
    # report). Everything else on this canvas is asserted against it.
    draw.text((text_x, 24), "GRAVEL GOD CYCLING", fill=SEC_BROWN, font=font_kicker)

    y = 52
    for line in lines:
        draw.text((text_x, y), line, fill=DARK_BROWN, font=font_name)
        y += name_line_h

    # Tier chip — dark text on gold (paper-on-gold fails AA; see report).
    chip_y = y + 8
    if state == "rated":
        tier_text = _tier_label(race)
        tw_chip = tw(draw, tier_text, font_tier) + 28
        th_chip = th(draw, tier_text, font_tier) + 16
        assert_contrast(DARK_BROWN, GOLD, font_tier.size, True, "tier chip")
        assert_type_floor(font_tier.size, "tier chip")
        draw.rectangle([text_x, chip_y, text_x + tw_chip, chip_y + th_chip], fill=GOLD)
        draw.text((text_x + 14, chip_y + 8), tier_text, fill=DARK_BROWN, font=font_tier)
        meta_x = text_x + tw_chip + 20
    else:
        meta_x = text_x
        th_chip = th(draw, "TIER", font_tier) + 16

    meta_parts = [p for p in (location.upper(), month, distance) if p]
    meta_line = "  ·  ".join(meta_parts)
    assert_contrast(SEC_BROWN, PAPER, font_meta.size, False, "meta line")
    assert_type_floor(font_meta.size, "meta line")
    draw.text((meta_x, chip_y + 4), meta_line, fill=SEC_BROWN, font=font_meta)

    # Score block, right side.
    if state == "rated":
        rating = race.get("gravel_god_rating") or race.get("rating")
        overall = rating["overall_score"]
        score_text = str(overall)
        slash_text = "/100"
        sw = tw(draw, score_text, font_score_big)
        slw = tw(draw, slash_text, font_score_slash)
        score_right = HEADER_W - margin
        assert_contrast(DARK_BROWN, PAPER, font_score_big.size, True, "score number")
        assert_type_floor(font_score_big.size, "score number")
        assert_type_floor(font_score_slash.size, "score /100")
        draw.text((score_right - sw - slw, 20), score_text, fill=DARK_BROWN, font=font_score_big)
        draw.text((score_right - slw, 20 + (font_score_big.size - font_score_slash.size)),
                   slash_text, fill=SEC_BROWN, font=font_score_slash)
        label_text = "RACE RATING"
        assert_contrast(GOLD_DEEP, PAPER, font_score_label.size, True, "RACE RATING label")
        assert_type_floor(font_score_label.size, "RACE RATING label")
        lw = tw(draw, label_text, font_score_label)
        draw.text((score_right - lw, 20 + font_score_big.size + 8), label_text,
                   fill=GOLD_DEEP, font=font_score_label)
    else:
        pending_text = "NOT YET RATED"
        assert_contrast(SEC_BROWN, PAPER, font_pending.size, True, "pending label")
        assert_type_floor(font_pending.size, "pending label")
        pw = tw(draw, pending_text, font_pending)
        draw.text((HEADER_W - margin - pw, 60), pending_text, fill=SEC_BROWN, font=font_pending)

    # Divider under top block.
    draw.rectangle([0, top_h - 1, HEADER_W, top_h + 1], fill=TAN_RULE)

    subscore_alt = ""
    if state == "rated":
        rating = race.get("gravel_god_rating") or race.get("rating")
        course_scores = {d: rating[d] for d in COURSE_DIMS}
        opinion_scores = {d: rating[d] for d in OPINION_DIMS}
        course_total = sum(course_scores.values())
        opinion_total = sum(opinion_scores.values())

        col_w = HEADER_W // 2
        radius = 150
        cy = top_h + 60 + radius
        draw_radar(img, col_w // 2, cy, radius, COURSE_DIMS, course_scores, TEAL,
                   "COURSE PROFILE", font_axis, font_axis, font_center, font_center_label, 35)
        draw.line([(col_w, top_h + 10), (col_w, top_h + radar_h - 30)], fill=TAN_RULE, width=1)
        draw_radar(img, col_w + col_w // 2, cy, radius, OPINION_DIMS, opinion_scores, GOLD_DEEP,
                   "EDITORIAL", font_axis, font_axis, font_center, font_center_label, 35)

        subscore_alt = "; ".join(
            f"{DIM_LABELS[d]} {course_scores[d]}/5" for d in COURSE_DIMS
        ) + "; " + "; ".join(
            f"{DIM_LABELS[d]} {opinion_scores[d]}/5" for d in OPINION_DIMS
        )

    # Bottom structural border.
    draw.rectangle([0, height - 3, HEADER_W, height], fill=DARK_BROWN)

    rgb = img.convert("RGB")

    if state == "rated":
        rating = race.get("gravel_god_rating") or race.get("rating")
        alt = (
            f"{name} — {_tier_label(race)} — GRAVEL GOD RATING by "
            f"gravelgodcycling.com: {rating['overall_score']}/100. "
            f"Course Profile {course_total}/35, Editorial {opinion_total}/35. {subscore_alt}."
        )
    else:
        alt = f"{name} — not yet rated by gravelgodcycling.com."

    return rgb, alt


# ── Includes image ───────────────────────────────────────────────

INCLUDES_W = 1240
TILE_H = 130
TILE_GAP = 16
TILE_MARGIN = 40
TILES_PER_ROW = 2


def build_includes_image(race: dict, plan_class: str, plan: dict, altitude_flag: bool):
    """Returns (PIL.Image RGB, alt_text str)."""
    name = race.get("display_name") or race.get("name") or race.get("slug")
    tier = plan.get("tier", plan_class)

    tiles = list(STANDARD_TILES)
    if altitude_flag:
        tiles.append(MODULE_TILES["altitude"])
    if plan_class == "masters":
        tiles.append(MODULE_TILES["masters"])

    n_rows = math.ceil(len(tiles) / TILES_PER_ROW)
    height = TILE_MARGIN * 2 + 70 + n_rows * TILE_H + (n_rows - 1) * TILE_GAP

    img = Image.new("RGB", (INCLUDES_W, height), PAPER)
    draw = ImageDraw.Draw(img)

    font_kicker = load_font(FONT_DATA_BOLD, 32)
    font_tile = load_font(FONT_EDITORIAL, 32)

    kicker = f"INSIDE THE {tier.upper()} PLAN"
    assert_contrast(GOLD_DEEP, PAPER, font_kicker.size, True, "includes kicker")
    assert_type_floor(font_kicker.size, "includes kicker")
    draw.text((TILE_MARGIN, TILE_MARGIN), kicker, fill=GOLD_DEEP, font=font_kicker)
    rule_y = TILE_MARGIN + 44
    draw.rectangle([TILE_MARGIN, rule_y, INCLUDES_W - TILE_MARGIN, rule_y + 3], fill=GOLD_DEEP)

    col_w = (INCLUDES_W - TILE_MARGIN * 2 - TILE_GAP) // TILES_PER_ROW
    grid_top = rule_y + 26

    tile_alts = []
    for idx, (icon_key, copy_text) in enumerate(tiles):
        row, col = divmod(idx, TILES_PER_ROW)
        x0 = TILE_MARGIN + col * (col_w + TILE_GAP)
        y0 = grid_top + row * (TILE_H + TILE_GAP)
        x1 = x0 + col_w
        y1 = y0 + TILE_H
        draw.rectangle([x0, y0, x1, y1], fill=WHITE, outline=TAN_BORDER, width=2)

        icon_box_size = 76
        icon_box = (x0 + 20, y0 + (TILE_H - icon_box_size) // 2,
                    x0 + 20 + icon_box_size, y0 + (TILE_H - icon_box_size) // 2 + icon_box_size)
        _asset_names = {"training": "cal", "heat": "flame", "skills": "skills",
                        "mental": "grit", "fueling": "bottle", "strength": "strength",
                        "altitude": "altitude", "masters": "masters", "women": "women"}
        _png = _png_asset(_asset_names.get(icon_key, icon_key), icon_box_size)
        if _png is not None:
            img.paste(_png, (icon_box[0] + (icon_box_size - _png.width) // 2, icon_box[1]), _png)
        else:
            ICON_DRAWERS[icon_key](draw, icon_box)

        text_x = icon_box[2] + 22
        text_max_w = x1 - text_x - 20
        assert_contrast(DARK_BROWN, WHITE, font_tile.size, False, f"tile copy ({icon_key})")
        assert_type_floor(font_tile.size, f"tile copy ({icon_key})")
        lines = wrap_lines(draw, copy_text, font_tile, text_max_w, max_lines=3)
        line_h = 38
        total_h = len(lines) * line_h
        text_y = y0 + (TILE_H - total_h) // 2
        for line in lines:
            draw.text((text_x, text_y), line, fill=DARK_BROWN, font=font_tile)
            text_y += line_h

        tile_alts.append(copy_text)

    draw.rectangle([0, 0, INCLUDES_W - 1, height - 1], outline=TAN_BORDER, width=1)

    alt = (
        f"{name} {tier} plan includes: " + "; ".join(tile_alts) + "."
    )
    return img, alt


# ── Output: hash-named files + decode-check ──────────────────────

def save_and_hash(img: "Image.Image", output_dir: Path, prefix: str) -> Path:
    import io
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90, optimize=True)
    data = buf.getvalue()
    content_hash = hashlib.sha256(data).hexdigest()[:8]
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{prefix}-{content_hash}.jpg"
    out_path.write_bytes(data)

    # Decode-check: reopen and fully decode pixel data.
    with Image.open(out_path) as check_img:
        check_img.load()
        if check_img.size != img.size:
            raise TPListingError(f"decode-check size mismatch for {out_path}")

    return out_path


# ── Manifest ───────────────────────────────────────────────────────

def load_manifest(path: Path) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"generator_version": GENERATOR_VERSION, "races": {}}


def save_manifest(manifest: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


# ── Orchestration ─────────────────────────────────────────────────

def generate_for_race(slug: str, plan_classes: list = None, data_dir: Path = DATA_DIR,
                       output_dir: Path = OUTPUT_DIR, plans_db_path: Path = DEFAULT_PLANS_DB,
                       manifest: dict = None) -> dict:
    """Generate the header image and one includes image per requested plan
    class for a race. Returns the manifest entry for this race (also merges
    into `manifest` if provided)."""
    race = load_race(slug, data_dir)
    altitude_flag = check_altitude_flag(race)

    header_img, header_alt = build_header_image(race)
    header_path = save_and_hash(header_img, output_dir, f"{slug}-header")

    entry = manifest["races"].setdefault(slug, {}) if manifest is not None else {}
    entry["header"] = {"file": header_path.name, "alt": header_alt}
    entry.setdefault("plans", {})

    all_plans = load_plans_db(plans_db_path)
    race_plans = plans_for_race(all_plans, slug)
    pub_plans = published_plans(race_plans)

    if plan_classes is None:
        available = sorted({plan_class_of(p) for p in pub_plans})
    else:
        available = plan_classes

    for pc in available:
        candidates = [p for p in pub_plans if plan_class_of(p) == pc]
        if not candidates:
            print(f"  SKIP: {slug}/{pc} (no published plan of this class)")
            continue
        # Prefer the longest published variant as the representative record.
        plan = max(candidates, key=lambda p: p.get("length_wk", 0))
        includes_img, includes_alt = build_includes_image(race, pc, plan, altitude_flag)
        includes_path = save_and_hash(includes_img, output_dir, f"{slug}-{pc}-includes")
        entry["plans"][pc] = {"file": includes_path.name, "alt": includes_alt}

    if manifest is not None:
        manifest["races"][slug] = entry

    return entry


def main():
    parser = argparse.ArgumentParser(description="Generate TP-listing images (header + includes)")
    parser.add_argument("--slug", help="Race slug (e.g. big-sugar)")
    parser.add_argument("--plan-class", action="append", dest="plan_classes",
                         help="Plan class to generate includes for (finisher, masters, compete, "
                              "time-crunched, save-my-race). Repeatable. Default: all published classes.")
    parser.add_argument("--all-p0", action="store_true", help="Generate the 8 P0 races")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--plans-db", type=Path, default=DEFAULT_PLANS_DB)
    args = parser.parse_args()

    if not args.slug and not args.all_p0:
        parser.error("Provide --slug or --all-p0")

    slugs = P0_SLUGS if args.all_p0 else [args.slug]
    manifest_path = args.output_dir / "manifest.json"
    manifest = load_manifest(manifest_path)

    errors = 0
    for slug in slugs:
        try:
            generate_for_race(slug, args.plan_classes, args.data_dir, args.output_dir,
                               args.plans_db, manifest)
            print(f"  OK: {slug}")
        except TPListingError as e:
            print(f"  ERROR: {slug}: {e}")
            errors += 1

    save_manifest(manifest, manifest_path)
    print(f"\nDone. {len(slugs) - errors}/{len(slugs)} races generated. Manifest: {manifest_path}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
