"""Zone spectrum bar chart overlay template for training zone infographics."""
from PIL import Image, ImageDraw

from .base import (
    load_font, hex_to_rgb, apply_brand_border,
    PRIMARY_BROWN, DARK_TEAL, TEAL, DARK_GOLD, GOLD, OFF_WHITE, BLACK, WHITE,
)

# Zone definitions: name, min%, max%, color
ZONES = [
    ("Z1 — Active Recovery", 0, 55, TEAL),
    ("Z2 — Endurance", 56, 75, DARK_TEAL),
    ("Z3 — Tempo", 76, 87, "#2B7A72"),
    ("Z4 — Threshold", 88, 95, DARK_GOLD),
    ("Z5 — VO2max", 96, 105, GOLD),
    ("Z6 — Anaerobic", 106, 120, PRIMARY_BROWN),
    ("Z7 — Neuromuscular", 121, 150, BLACK),
]


def render(width: int = 1200, height: int = 600) -> Image.Image:
    """Render a zone spectrum bar chart."""
    img = Image.new("RGB", (width, height), hex_to_rgb(OFF_WHITE))
    draw = ImageDraw.Draw(img)

    font_label = load_font(bold=True, size=16)
    font_pct = load_font(bold=False, size=14)
    font_title = load_font(bold=True, size=22)

    # Title
    draw.text((40, 24), "TRAINING ZONE SPECTRUM", fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.line([(40, 58), (width - 40, 58)], fill=hex_to_rgb(BLACK), width=2)

    # Bar area
    bar_top = 80
    bar_height = 50
    gap = 14
    bar_left = 280
    bar_right = width - 100
    max_pct = 150  # max zone upper bound

    for i, (name, min_pct, max_pct_val, color) in enumerate(ZONES):
        y = bar_top + i * (bar_height + gap)

        # Label
        draw.text((40, y + 14), name, fill=hex_to_rgb(BLACK), font=font_label)

        # Bar background
        draw.rectangle([(bar_left, y), (bar_right, y + bar_height)],
                       outline=hex_to_rgb(BLACK), width=1, fill=hex_to_rgb("#e8e0d8"))

        # Filled bar
        fill_width = int((max_pct_val / max_pct) * (bar_right - bar_left))
        draw.rectangle([(bar_left, y), (bar_left + fill_width, y + bar_height)],
                       fill=hex_to_rgb(color))

        # Percentage label
        pct_text = f"{min_pct}-{max_pct_val}%"
        draw.text((bar_right + 10, y + 16), pct_text, fill=hex_to_rgb(BLACK), font=font_pct)

    return apply_brand_border(img)
