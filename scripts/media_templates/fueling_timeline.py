"""Race-day fueling timeline — horizontal timeline with 5 milestones."""
from PIL import Image, ImageDraw

from .base import (
    load_font, hex_to_rgb,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, DARK_GOLD,
    OFF_WHITE, BLACK, WHITE,
)

MUTED_TAN = "#c4b5ab"

MILESTONES = [
    {
        "time": "T-3hrs",
        "label": "Pre-Race Meal",
        "detail": "500-800 cal\n2-3g carbs/kg",
    },
    {
        "time": "T-30min",
        "label": "Pre-Start Gel",
        "detail": "25g carbs\n200ml water",
    },
    {
        "time": "0-30min",
        "label": "Settle In",
        "detail": "Sip only\nFind rhythm",
    },
    {
        "time": "30min+",
        "label": "Fueling Zone",
        "detail": "60-90g carbs/hr\nSet a timer",
    },
    {
        "time": "Ongoing",
        "label": "Hydration",
        "detail": "500-750ml/hr\n+ electrolytes",
    },
]


def render(width: int = 1200, height: int = 500) -> Image.Image:
    """Render a horizontal fueling timeline."""
    img = Image.new("RGB", (width, height), hex_to_rgb(OFF_WHITE))
    draw = ImageDraw.Draw(img)

    font_title = load_font(bold=True, size=22)
    font_subtitle = load_font(bold=False, size=13)
    font_time = load_font(bold=True, size=16)
    font_label = load_font(bold=True, size=14)
    font_detail = load_font(bold=False, size=12)
    font_xs = load_font(bold=False, size=11)

    pad = 40

    # Title
    draw.text((pad, 16), "RACE-DAY FUELING TIMELINE",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.text((pad + 400, 20), "Don't bonk. Fuel by the clock.",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_subtitle)
    draw.line([(pad, 48), (width - pad, 48)], fill=hex_to_rgb(BLACK), width=2)

    # Timeline bar
    n = len(MILESTONES)
    bar_y = 220
    bar_h = 8
    bar_left = pad + 60
    bar_right = width - pad - 60

    draw.rectangle([(bar_left, bar_y), (bar_right, bar_y + bar_h)],
                   fill=hex_to_rgb(PRIMARY_BROWN))

    # Milestone positions
    spacing = (bar_right - bar_left) / (n - 1)

    for i, ms in enumerate(MILESTONES):
        cx = int(bar_left + i * spacing)

        # Circle on timeline
        r = 14
        draw.ellipse([(cx - r, bar_y + bar_h // 2 - r),
                       (cx + r, bar_y + bar_h // 2 + r)],
                      fill=hex_to_rgb(DARK_TEAL),
                      outline=hex_to_rgb(BLACK), width=2)

        # Callout box ABOVE timeline
        box_w = 160
        box_h = 80
        box_x = cx - box_w // 2
        box_y = bar_y - 140

        # Clamp to stay within image
        box_x = max(pad, min(box_x, width - pad - box_w))

        draw.rectangle([(box_x, box_y), (box_x + box_w, box_y + box_h)],
                       fill=hex_to_rgb(DARK_GOLD if i in (0, 3, 4) else WHITE),
                       outline=hex_to_rgb(BLACK), width=2)

        # Connector line from box to circle
        draw.line([(cx, box_y + box_h), (cx, bar_y + bar_h // 2 - r)],
                  fill=hex_to_rgb(BLACK), width=1)

        # Text in callout
        text_color = WHITE if i in (0, 3, 4) else BLACK
        # Detail text (multi-line)
        lines = ms["detail"].split("\n")
        for j, line in enumerate(lines):
            draw.text((box_x + 10, box_y + 8 + j * 18), line,
                      fill=hex_to_rgb(text_color), font=font_detail)

        # Time label BELOW timeline
        time_y = bar_y + bar_h + 24
        bbox = draw.textbbox((0, 0), ms["time"], font=font_time)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, time_y), ms["time"],
                  fill=hex_to_rgb(DARK_TEAL), font=font_time)

        # Label below time
        label_y = time_y + 24
        bbox = draw.textbbox((0, 0), ms["label"], font=font_label)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, label_y), ms["label"],
                  fill=hex_to_rgb(BLACK), font=font_label)

    # Source
    draw.text((pad, height - 20), "gravelgodcycling.com",
              fill=hex_to_rgb(MUTED_TAN), font=font_xs)

    return img
