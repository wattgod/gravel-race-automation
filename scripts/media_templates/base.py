"""Base constants and utilities for media template post-processing."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ── Brand Colors (from tokens.css) ───────────────────────
PRIMARY_BROWN = "#59473c"
SECONDARY_BROWN = "#8c7568"
DARK_TEAL = "#1A8A82"
TEAL = "#4ECDC4"
GOLD = "#B7950B"
LIGHT_GOLD = "#c9a92c"
WARM_PAPER = "#f5efe6"
DARK_BROWN = "#3a2e25"       # Borders, outlines
NEAR_BLACK = "#1a1613"       # Body text on light backgrounds
WHITE = "#FFFFFF"

# ── Extended Brand Colors ─────────────────────────────────
WARM_BROWN = "#A68E80"       # Caption/source text
TAN = "#d4c5b9"             # Subtle decorative
ERROR_RED = "#c0392b"        # Danger/alert
SAND = "#ede4d8"             # Alternating/subtle backgrounds
TIER_3 = "#999999"           # T3 tier color (legacy cold grey)
TIER_4 = "#cccccc"           # T4 tier color (legacy cold grey)
TIER_3_WARM = "#766a5e"      # T3 warm — earthy olive-brown (matches search widget)
TIER_4_WARM = "#5e6868"      # T4 warm — muted teal-grey (matches search widget)

# ── Font Paths ────────────────────────────────────────────
FONTS_DIR = Path(__file__).parent.parent.parent / "guide" / "fonts"
FONT_REGULAR = FONTS_DIR / "SometypeMono-Regular.ttf"
FONT_BOLD = FONTS_DIR / "SometypeMono-Bold.ttf"
FONT_EDITORIAL = FONTS_DIR / "SourceSerif4-Variable.ttf"


def load_font(bold: bool = False, size: int = 14) -> ImageFont.FreeTypeFont:
    """Load Sometype Mono font at the given size."""
    path = FONT_BOLD if bold else FONT_REGULAR
    if not path.exists():
        # Fallback to default font if TTF not available
        return ImageFont.load_default()
    return ImageFont.truetype(str(path), size)


def load_editorial_font(size: int = 22, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Load Source Serif 4 for editorial titles."""
    if not FONT_EDITORIAL.exists():
        return load_font(bold=bold, size=size)
    font = ImageFont.truetype(str(FONT_EDITORIAL), size)
    try:
        font.set_variation_by_axes([700 if bold else 400])
    except (AttributeError, OSError):
        pass  # Pillow version may not support variable axes
    return font


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color string to RGB tuple."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def draw_gold_rule(draw: ImageDraw.ImageDraw, x1: int, y: int, x2: int, width: int = 2):
    """Gold accent line under titles — editorial feel."""
    draw.line([(x1, y), (x2, y)], fill=hex_to_rgb(GOLD), width=width)


def apply_brand_border(img: Image.Image, width: int = 3, color: str = DARK_BROWN) -> Image.Image:
    """Apply a solid border around the image."""
    rgb = hex_to_rgb(color)
    bordered = Image.new("RGB", (img.width + width * 2, img.height + width * 2), rgb)
    bordered.paste(img, (width, width))
    return bordered
