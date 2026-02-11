"""Three acts of a long gravel race — three vertical panels."""
from PIL import Image, ImageDraw

from .base import (
    load_font, hex_to_rgb,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, DARK_GOLD,
    OFF_WHITE, BLACK, WHITE,
)

MUTED_TAN = "#c4b5ab"

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
        "color": DARK_GOLD,
        "text_color": BLACK,
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
    img = Image.new("RGB", (width, height), hex_to_rgb(OFF_WHITE))
    draw = ImageDraw.Draw(img)

    font_title = load_font(bold=True, size=22)
    font_subtitle = load_font(bold=False, size=13)
    font_act = load_font(bold=True, size=18)
    font_range = load_font(bold=True, size=28)
    font_bullet = load_font(bold=False, size=14)
    font_xs = load_font(bold=False, size=11)

    pad = 40

    # Title
    draw.text((pad, 16), "THE THREE ACTS OF GRAVEL RACING",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.text((pad + 480, 20), "Survive. Execute. Capitalize.",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_subtitle)
    draw.line([(pad, 48), (width - pad, 48)], fill=hex_to_rgb(BLACK), width=2)

    # Three panels
    n = len(ACTS)
    panel_gap = 0  # Thick borders serve as separators
    panel_top = 64
    panel_bottom = height - 40
    panel_h = panel_bottom - panel_top
    total_w = width - pad * 2
    panel_w = total_w // n

    for i, act in enumerate(ACTS):
        x = pad + i * panel_w
        color = act["color"]
        tc = act["text_color"]

        # Panel background
        draw.rectangle([(x, panel_top), (x + panel_w, panel_bottom)],
                       fill=hex_to_rgb(color), outline=hex_to_rgb(BLACK), width=3)

        # Act name
        draw.text((x + 20, panel_top + 20), act["name"],
                  fill=hex_to_rgb(tc), font=font_act)

        # Percentage range — big
        draw.text((x + 20, panel_top + 56), act["range"],
                  fill=hex_to_rgb(tc), font=font_range)

        # Divider
        div_y = panel_top + 100
        draw.line([(x + 20, div_y), (x + panel_w - 20, div_y)],
                  fill=hex_to_rgb(tc), width=1)

        # Strategies as bullet points
        for j, strat in enumerate(act["strategies"]):
            sy = div_y + 20 + j * 36
            # Bullet marker
            draw.text((x + 20, sy), ">",
                      fill=hex_to_rgb(tc), font=font_bullet)
            draw.text((x + 40, sy), strat,
                      fill=hex_to_rgb(tc), font=font_bullet)

    # Source
    draw.text((pad, height - 20), "gravelgodcycling.com",
              fill=hex_to_rgb(MUTED_TAN), font=font_xs)

    return img
