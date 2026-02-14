"""Zone spectrum bar chart overlay template for training zone infographics."""
from PIL import Image, ImageDraw

from .base import (
    load_font, load_editorial_font, hex_to_rgb, draw_gold_rule,
    PRIMARY_BROWN, SECONDARY_BROWN, WARM_BROWN, SAND,
    DARK_TEAL, TEAL, GOLD, LIGHT_GOLD, WARM_PAPER, DARK_BROWN, NEAR_BLACK, WHITE,
)

BASE_WIDTH = 1200

# Zone definitions: name, min%, max%, color
ZONES = [
    ("Z1 — Active Recovery", 0, 55, TEAL),
    ("Z2 — Endurance", 56, 75, DARK_TEAL),
    ("Z3 — Tempo", 76, 87, DARK_TEAL),
    ("Z4 — Threshold", 88, 95, GOLD),
    ("Z5 — VO2max", 96, 105, LIGHT_GOLD),
    ("Z6 — Anaerobic", 106, 120, PRIMARY_BROWN),
    ("Z7 — Neuromuscular", 121, 150, DARK_BROWN),
]


def render(width: int = 1200, height: int = 600) -> Image.Image:
    """Render a zone spectrum bar chart."""
    s = width / BASE_WIDTH

    img = Image.new("RGB", (width, height), hex_to_rgb(WARM_PAPER))
    draw = ImageDraw.Draw(img)

    font_label = load_font(bold=True, size=int(16 * s))
    font_pct = load_font(bold=False, size=int(14 * s))
    font_title = load_editorial_font(size=int(26 * s))

    pad = int(40 * s)

    # Title — Source Serif 4 + gold rule
    draw.text((pad, int(18 * s)), "TRAINING ZONE SPECTRUM", fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    rule_y = int(54 * s)
    draw_gold_rule(draw, pad, rule_y, width - pad, width=max(2, int(2 * s)))

    # Bar area
    bar_top = int(80 * s)
    bar_height = int(50 * s)
    gap = int(14 * s)
    bar_left = int(280 * s)
    bar_right = width - int(100 * s)
    max_pct = 150  # max zone upper bound

    for i, (name, min_pct, max_pct_val, color) in enumerate(ZONES):
        y = bar_top + i * (bar_height + gap)

        # Label
        draw.text((pad, y + int(14 * s)), name, fill=hex_to_rgb(NEAR_BLACK), font=font_label)

        # Bar background
        draw.rectangle([(bar_left, y), (bar_right, y + bar_height)],
                       outline=hex_to_rgb(DARK_BROWN), width=max(1, int(1 * s)), fill=hex_to_rgb(SAND))

        # Filled bar
        fill_width = int((max_pct_val / max_pct) * (bar_right - bar_left))
        draw.rectangle([(bar_left, y), (bar_left + fill_width, y + bar_height)],
                       fill=hex_to_rgb(color))

        # Percentage label
        pct_text = f"{min_pct}-{max_pct_val}%"
        draw.text((bar_right + int(10 * s), y + int(16 * s)), pct_text, fill=hex_to_rgb(NEAR_BLACK), font=font_pct)

    return img
