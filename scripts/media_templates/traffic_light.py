"""Traffic light autoregulation system — Green / Yellow / Red."""
from PIL import Image, ImageDraw

from .base import (
    load_font, load_editorial_font, hex_to_rgb, draw_gold_rule,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, GOLD,
    LIGHT_GOLD, WARM_BROWN, ERROR_RED, WARM_PAPER, DARK_BROWN, NEAR_BLACK, WHITE,
)

LIGHTS = [
    {
        "name": "GREEN",
        "color": DARK_TEAL,
        "subtitle": "PROCEED AS PLANNED",
        "criteria": [
            "Slept 7+ hours",
            "Resting HR normal",
            "Motivation is there",
            "No unusual soreness",
        ],
        "action": "Execute the workout as written.",
    },
    {
        "name": "YELLOW",
        "color": LIGHT_GOLD,
        "text_color": NEAR_BLACK,
        "subtitle": "MODIFY",
        "criteria": [
            "Slept <6 hours",
            "Resting HR elevated 5-10%",
            "Feeling flat or sluggish",
            "Minor soreness or fatigue",
        ],
        "action": "Reduce intensity 5-10% or cut volume 20%.",
    },
    {
        "name": "RED",
        "color": ERROR_RED,
        "subtitle": "SKIP OR REPLACE",
        "criteria": [
            "Slept <5 hours",
            "Resting HR elevated 10%+",
            "Illness symptoms",
            "Sharp pain or injury risk",
        ],
        "action": "Replace with Z1 spin or full rest day.",
    },
]

BASE_WIDTH = 1200


def render(width: int = 1200, height: int = 800) -> Image.Image:
    """Render the traffic light autoregulation system."""
    s = width / BASE_WIDTH

    img = Image.new("RGB", (width, height), hex_to_rgb(WARM_PAPER))
    draw = ImageDraw.Draw(img)

    font_title = load_editorial_font(size=int(26 * s))
    font_light = load_font(bold=True, size=int(20 * s))
    font_sub = load_font(bold=True, size=int(14 * s))
    font_label = load_font(bold=False, size=int(14 * s))
    font_action = load_font(bold=True, size=int(13 * s))

    pad = int(40 * s)

    # Title — Source Serif 4 + gold rule
    draw.text((pad, int(14 * s)), "DAILY AUTOREGULATION: CHECK BEFORE EVERY SESSION",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    rule_y = int(50 * s)
    draw_gold_rule(draw, pad, rule_y, width - pad, width=max(2, int(2 * s)))

    # Three light sections
    section_h = int(210 * s)
    section_gap = int(18 * s)
    section_top = int(70 * s)

    for i, light in enumerate(LIGHTS):
        y = section_top + i * (section_h + section_gap)
        color = light["color"]

        # Traffic light SQUARE (no circles — brand rule)
        sq_cx = pad + int(50 * s)
        sq_cy = y + section_h // 2
        sq_half = int(40 * s)
        draw.rectangle([(sq_cx - sq_half, sq_cy - sq_half),
                        (sq_cx + sq_half, sq_cy + sq_half)],
                       fill=hex_to_rgb(color), outline=hex_to_rgb(DARK_BROWN),
                       width=max(3, int(3 * s)))

        # Light name inside square
        name = light["name"]
        bbox = draw.textbbox((0, 0), name, font=font_sub)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        name_color = NEAR_BLACK if color in (LIGHT_GOLD, GOLD) else WHITE
        draw.text((sq_cx - tw // 2, sq_cy - th // 2 - int(1 * s)),
                  name, fill=hex_to_rgb(name_color), font=font_sub)

        # Content area
        content_x = pad + int(120 * s)

        # Card background
        draw.rectangle([(content_x, y), (width - pad, y + section_h)],
                       fill=hex_to_rgb(WHITE), outline=hex_to_rgb(DARK_BROWN),
                       width=max(2, int(2 * s)))

        # Colored top strip
        strip_h = int(36 * s)
        draw.rectangle([(content_x, y), (width - pad, y + strip_h)],
                       fill=hex_to_rgb(color))
        draw.text((content_x + int(14 * s), y + int(8 * s)), light["subtitle"],
                  fill=hex_to_rgb(NEAR_BLACK if color in (LIGHT_GOLD, GOLD) else WHITE), font=font_light)

        # Criteria list
        criteria_y = y + strip_h + int(14 * s)
        for j, criterion in enumerate(light["criteria"]):
            cy = criteria_y + j * int(26 * s)
            # Square bullet
            draw.rectangle([(content_x + int(16 * s), cy + int(4 * s)),
                            (content_x + int(24 * s), cy + int(12 * s))],
                           fill=hex_to_rgb(color))
            draw.text((content_x + int(34 * s), cy), criterion,
                      fill=hex_to_rgb(NEAR_BLACK), font=font_label)

        # Action line
        action_y = y + section_h - int(34 * s)
        draw.text((content_x + int(16 * s), action_y), light["action"],
                  fill=hex_to_rgb(color), font=font_action)

    return img
