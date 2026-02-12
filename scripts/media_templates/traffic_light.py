"""Traffic light autoregulation system — Green / Yellow / Red."""
from PIL import Image, ImageDraw

from .base import (
    load_font, hex_to_rgb,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, DARK_GOLD,
    GOLD, OFF_WHITE, BLACK, WHITE,
)

MUTED_TAN = "#c4b5ab"
RED = "#c0392b"
GREEN = "#178079"
YELLOW = "#F4D03F"

LIGHTS = [
    {
        "name": "GREEN",
        "color": GREEN,
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
        "color": YELLOW,
        "text_color": BLACK,
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
        "color": RED,
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


def render(width: int = 1200, height: int = 800) -> Image.Image:
    """Render the traffic light autoregulation system."""
    img = Image.new("RGB", (width, height), hex_to_rgb(OFF_WHITE))
    draw = ImageDraw.Draw(img)

    font_title = load_font(bold=True, size=22)
    font_light = load_font(bold=True, size=20)
    font_sub = load_font(bold=True, size=14)
    font_label = load_font(bold=False, size=14)
    font_action = load_font(bold=True, size=13)
    font_xs = load_font(bold=False, size=11)

    pad = 40

    # Title
    draw.text((pad, 18), "DAILY AUTOREGULATION: CHECK BEFORE EVERY SESSION",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.line([(pad, 50), (width - pad, 50)], fill=hex_to_rgb(BLACK), width=2)

    # Three light sections
    section_h = 210
    section_gap = 18
    section_top = 70

    for i, light in enumerate(LIGHTS):
        y = section_top + i * (section_h + section_gap)
        color = light["color"]
        text_color = light.get("text_color", WHITE)

        # Traffic light circle
        circle_x = pad + 50
        circle_y = y + section_h // 2
        circle_r = 40
        draw.ellipse([(circle_x - circle_r, circle_y - circle_r),
                       (circle_x + circle_r, circle_y + circle_r)],
                      fill=hex_to_rgb(color), outline=hex_to_rgb(BLACK), width=3)

        # Light name inside circle
        name = light["name"]
        bbox = draw.textbbox((0, 0), name, font=font_sub)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        name_color = BLACK if color == YELLOW else WHITE
        draw.text((circle_x - tw // 2, circle_y - th // 2 - 1),
                  name, fill=hex_to_rgb(name_color), font=font_sub)

        # Content area
        content_x = pad + 120
        content_w = width - content_x - pad

        # Card background
        draw.rectangle([(content_x, y), (width - pad, y + section_h)],
                       fill=hex_to_rgb(WHITE), outline=hex_to_rgb(BLACK), width=2)

        # Colored top strip
        strip_h = 36
        draw.rectangle([(content_x, y), (width - pad, y + strip_h)],
                       fill=hex_to_rgb(color))
        draw.text((content_x + 14, y + 8), light["subtitle"],
                  fill=hex_to_rgb(BLACK if color == YELLOW else WHITE), font=font_light)

        # Criteria list
        criteria_y = y + strip_h + 14
        for j, criterion in enumerate(light["criteria"]):
            cy = criteria_y + j * 26
            # Bullet
            draw.rectangle([(content_x + 16, cy + 4), (content_x + 24, cy + 12)],
                           fill=hex_to_rgb(color))
            draw.text((content_x + 34, cy), criterion,
                      fill=hex_to_rgb(BLACK), font=font_label)

        # Action line
        action_y = y + section_h - 34
        draw.text((content_x + 16, action_y), light["action"],
                  fill=hex_to_rgb(color), font=font_action)

    # Source
    draw.text((pad, height - 18), "gravelgodcycling.com", fill=hex_to_rgb(MUTED_TAN), font=font_xs)

    return img
