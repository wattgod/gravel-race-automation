"""Base constants and utilities for media template post-processing."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ── Brand Colors ──────────────────────────────────────────
PRIMARY_BROWN = "#59473c"
SECONDARY_BROWN = "#8c7568"
DARK_TEAL = "#1A8A82"
TEAL = "#4ECDC4"
DARK_GOLD = "#B7950B"
GOLD = "#F4D03F"
OFF_WHITE = "#f5f0eb"
BLACK = "#000000"
WHITE = "#FFFFFF"

# ── Font Paths ────────────────────────────────────────────
FONTS_DIR = Path(__file__).parent.parent.parent / "guide" / "fonts"
FONT_REGULAR = FONTS_DIR / "SometypeMono-Regular.ttf"
FONT_BOLD = FONTS_DIR / "SometypeMono-Bold.ttf"


def load_font(bold: bool = False, size: int = 14) -> ImageFont.FreeTypeFont:
    """Load Sometype Mono font at the given size."""
    path = FONT_BOLD if bold else FONT_REGULAR
    if not path.exists():
        # Fallback to default font if TTF not available
        return ImageFont.load_default()
    return ImageFont.truetype(str(path), size)


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color string to RGB tuple."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def apply_brand_border(img: Image.Image, width: int = 3, color: str = BLACK) -> Image.Image:
    """Apply a solid border around the image."""
    rgb = hex_to_rgb(color)
    bordered = Image.new("RGB", (img.width + width * 2, img.height + width * 2), rgb)
    bordered.paste(img, (width, width))
    return bordered
