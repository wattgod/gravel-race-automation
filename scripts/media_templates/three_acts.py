"""Three acts of a long gravel race — three vertical panels."""
from PIL import Image, ImageDraw

from .base import (
    load_font, load_editorial_font, hex_to_rgb, draw_gold_rule,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, GOLD,
    WARM_PAPER, DARK_BROWN, NEAR_BLACK, WHITE, WARM_BROWN,
)

ACTS = [
    {
        "name": "ACT 1: RESTRAINT",
        "range": "0-33%",
        "color": DARK_TEAL,
        "text_color": WHITE,
        "strategies": [
            "Don't chase attacks",
            "Fuel early — first 30 min",
            "Find sustainable group",
        ],
    },
    {
        "name": "ACT 2: RESILIENCE",
        "range": "33-66%",
        "color": GOLD,
        "text_color": NEAR_BLACK,
        "strategies": [
            "Stay disciplined on nutrition",
            "Do your share, no hero pulls",
            "Exit this phase feeling good",
        ],
    },
    {
        "name": "ACT 3: RESOLVE",
        "range": "66-100%",
        "color": PRIMARY_BROWN,
        "text_color": WHITE,
        "strategies": [
            "Empty the tank",
            "Pass fading riders steadily",
            "Maintain pace — don't surge",
        ],
    },
]


def render(width: int = 1200, height: int = 600) -> Image.Image:
    """Render three vertical panels for race acts."""
    s = width / 1200

    img = Image.new("RGB", (width, height), hex_to_rgb(WARM_PAPER))
    draw = ImageDraw.Draw(img)

    font_title = load_editorial_font(size=int(26 * s))
    font_subtitle = load_font(bold=False, size=int(13 * s))
    font_act = load_font(bold=True, size=int(18 * s))
    font_range = load_font(bold=True, size=int(28 * s))
    font_bullet = load_font(bold=False, size=int(14 * s))

    pad = int(40 * s)

    # Title — Source Serif 4 + gold rule
    draw.text((pad, int(14 * s)), "THE THREE ACTS OF GRAVEL RACING",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.text((pad + int(500 * s), int(22 * s)), "Survive. Execute. Capitalize.",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_subtitle)
    rule_y = int(50 * s)
    draw_gold_rule(draw, pad, rule_y, width - pad, width=max(2, int(2 * s)))

    # Three panels
    n = len(ACTS)
    panel_gap = 0  # Thick borders serve as separators
    panel_top = int(64 * s)
    panel_bottom = height - int(40 * s)
    panel_h = panel_bottom - panel_top
    total_w = width - pad * 2
    panel_w = total_w // n

    for i, act in enumerate(ACTS):
        x = pad + i * panel_w
        color = act["color"]
        tc = act["text_color"]

        # Panel background
        draw.rectangle([(x, panel_top), (x + panel_w, panel_bottom)],
                       fill=hex_to_rgb(color), outline=hex_to_rgb(DARK_BROWN),
                       width=max(3, int(3 * s)))

        # Act name
        draw.text((x + int(20 * s), panel_top + int(20 * s)), act["name"],
                  fill=hex_to_rgb(tc), font=font_act)

        # Percentage range — big
        draw.text((x + int(20 * s), panel_top + int(56 * s)), act["range"],
                  fill=hex_to_rgb(tc), font=font_range)

        # Divider
        div_y = panel_top + int(100 * s)
        draw.line([(x + int(20 * s), div_y), (x + panel_w - int(20 * s), div_y)],
                  fill=hex_to_rgb(tc), width=max(1, int(1 * s)))

        # Strategies as bullet points
        for j, strat in enumerate(act["strategies"]):
            sy = div_y + int(20 * s) + j * int(36 * s)
            # Bullet marker
            draw.text((x + int(20 * s), sy), ">",
                      fill=hex_to_rgb(tc), font=font_bullet)
            draw.text((x + int(40 * s), sy), strat,
                      fill=hex_to_rgb(tc), font=font_bullet)

    return img
