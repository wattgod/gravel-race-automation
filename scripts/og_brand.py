#!/usr/bin/env python3
"""
2026 brand system for Gravel God Open Graph share cards (1200x630).

The cards mirror the live site, not a separate "social" look: warm-paper
ground, the 2026 GG mark top-left with the domain where the nav sits, a gold
rule under that header row, Source Serif 4 headlines, Sometype Mono
letter-spaced labels. Colors are the tokens from wordpress/brand_tokens.py.

History: the Feb-2026 cards (dark near-black ground, brown footer bar, gold
"G" box) predate the July 2026 rebrand and were never regenerated, so every
shared link showed the old logo, a palette the site no longer uses, and stale
numbers (race scores and catalog counts frozen at February values).

Shared by:
    scripts/generate_homepage_og.py  — /og/homepage.jpg (site-wide fallback)
    scripts/generate_og_images.py    — /og/{race-slug}.jpg
    scripts/generate_page_og.py      — /og/{page}.jpg for non-race pages
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630

REPO_ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = REPO_ROOT / "guide" / "fonts"
FONT_EDITORIAL = str(FONT_DIR / "SourceSerif4-Variable.ttf")
FONT_DATA = str(FONT_DIR / "SometypeMono-Regular.ttf")
FONT_DATA_BOLD = str(FONT_DIR / "SometypeMono-Bold.ttf")
LOGO_PNG = REPO_ROOT / "wordpress" / "assets" / "tp" / "logo.png"

# ── Tokens (wordpress/brand_tokens.py :root) ────────────────────
WARM_PAPER = (245, 239, 230)   # --gg-color-warm-paper  #f5efe6
SAND = (237, 228, 216)         # --gg-color-sand        #ede4d8
TAN = (212, 197, 185)          # --gg-color-tan         #d4c5b9
DARK_BROWN = (58, 46, 37)      # --gg-color-dark-brown  #3a2e25
PRIMARY_BROWN = (89, 71, 60)   # --gg-color-primary-brown #59473c
SEC_BROWN = (125, 105, 93)     # --gg-color-secondary-brown #7d695d
GOLD = (154, 126, 10)          # --gg-color-gold        #9a7e0a
TEAL = (23, 128, 121)          # --gg-color-teal        #178079
NEAR_BLACK = (26, 22, 19)      # --gg-color-near-black  #1a1613

MARGIN = 64
HEADER_RULE_Y = 132            # gold rule under the logo row, like the site header
DOMAIN = "GRAVELGODCYCLING.COM"


class OGCardError(Exception):
    """Raised instead of silently clipping or dropping card content."""


# ── Contrast (WCAG AA) ──────────────────────────────────────────

def _lin(c: int) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def contrast_ratio(a: tuple, b: tuple) -> float:
    la = 0.2126 * _lin(a[0]) + 0.7152 * _lin(a[1]) + 0.0722 * _lin(a[2])
    lb = 0.2126 * _lin(b[0]) + 0.7152 * _lin(b[1]) + 0.0722 * _lin(b[2])
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# ── Fonts ───────────────────────────────────────────────────────

_FONTS: dict = {}


def serif(size: int, weight: int = 700) -> ImageFont.FreeTypeFont:
    """Source Serif 4 at a given weight; optical size follows the px size."""
    key = ("serif", size, weight)
    if key not in _FONTS:
        f = ImageFont.truetype(FONT_EDITORIAL, size)
        f.set_variation_by_axes([weight, max(8, min(60, size))])
        _FONTS[key] = f
    return _FONTS[key]


def mono(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = ("mono", size, bold)
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(FONT_DATA_BOLD if bold else FONT_DATA, size)
    return _FONTS[key]


def text_w(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    l, _, r, _ = draw.textbbox((0, 0), text, font=font)
    return r - l


def tracked_w(draw, text: str, font, tracking: int) -> int:
    if not text:
        return 0
    return sum(text_w(draw, ch, font) for ch in text) + tracking * (len(text) - 1)


def draw_tracked(draw, xy, text: str, font, fill, tracking: int) -> int:
    """Draw letter-spaced text (CSS letter-spacing). Returns the end x."""
    x, y = xy
    for i, ch in enumerate(text):
        draw.text((x, y), ch, font=font, fill=fill)
        x += text_w(draw, ch, font) + (tracking if i < len(text) - 1 else 0)
    return x


def wrap(draw, text: str, font, max_w: int, max_lines: int) -> list[str]:
    """Greedy word wrap that refuses to drop words."""
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and text_w(draw, trial, font) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        raise OGCardError(f"{text!r} needs {len(lines)} lines, max {max_lines}")
    return lines


def fit_headline(draw, text: str, max_w: int, sizes=(96, 84, 76, 68, 60, 54),
                 max_lines: int = 2, weight: int = 700):
    """Largest headline size at which the text fits in max_lines."""
    for size in sizes:
        font = serif(size, weight)
        try:
            return font, wrap(draw, text, font, max_w, max_lines)
        except OGCardError:
            continue
    raise OGCardError(f"headline does not fit at {sizes[-1]}px: {text!r}")


# ── Logo ────────────────────────────────────────────────────────

_LOGO: dict = {}


def logo(height: int) -> Image.Image:
    """The 2026 GG mark (dark brown, transparent), trimmed and scaled."""
    if height not in _LOGO:
        src = Image.open(LOGO_PNG).convert("RGBA")
        src = src.crop(src.getbbox())
        w = round(src.width * height / src.height)
        _LOGO[height] = src.resize((w, height), Image.LANCZOS)
    return _LOGO[height]


# ── Frame ───────────────────────────────────────────────────────

def new_card() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Paper card with the site chrome: gold top line, GG mark + domain
    header row, gold rule beneath it."""
    img = Image.new("RGB", (W, H), WARM_PAPER)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 5], fill=GOLD)

    mark = logo(68)
    mark_y = (5 + HEADER_RULE_Y - mark.height) // 2 + 2
    img.paste(mark, (MARGIN, mark_y), mark)

    f = mono(18, bold=True)
    dw = tracked_w(draw, DOMAIN, f, 3)
    draw_tracked(draw, (W - MARGIN - dw, mark_y + mark.height // 2 - 11),
                 DOMAIN, f, DARK_BROWN, 3)

    draw.rectangle([0, HEADER_RULE_Y, W, HEADER_RULE_Y + 2], fill=GOLD)
    return img, draw


def kicker(draw, xy, parts: list[tuple[str, tuple]], size: int = 20) -> int:
    """Letter-spaced mono label line, e.g. [("TIER 1", SEC_BROWN), ...].
    Returns the end x."""
    f = mono(size, bold=True)
    x, y = xy
    for i, (text, color) in enumerate(parts):
        if i:
            x = draw_tracked(draw, (x + 14, y), "·", f, SEC_BROWN, 0) + 14
        x = draw_tracked(draw, (x, y), text.upper(), f, color, 4)
    return x


def save(img: Image.Image, path: Path) -> Path:
    path = Path(path).with_suffix(".jpg")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=90, optimize=True)
    return path


# Every text/ground pair the cards use must clear AA at its rendered size.
# Gold and teal only ever set >=18px bold labels or display numerals, so the
# 3:1 large-text bar applies to them; body ink needs 4.5:1.
for _fg, _min in ((DARK_BROWN, 4.5), (NEAR_BLACK, 4.5), (PRIMARY_BROWN, 4.5),
                  (SEC_BROWN, 4.5), (TEAL, 3.0), (GOLD, 3.0)):
    assert contrast_ratio(_fg, WARM_PAPER) >= _min, (_fg, contrast_ratio(_fg, WARM_PAPER))
