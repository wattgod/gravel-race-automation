"""Race-day fueling timeline — horizontal timeline with 5 milestones."""
from PIL import Image, ImageDraw

from .base import (
    load_font, load_editorial_font, hex_to_rgb, draw_gold_rule,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, GOLD,
    WARM_PAPER, DARK_BROWN, NEAR_BLACK, WHITE, WARM_BROWN,
)

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
    s = width / 1200

    img = Image.new("RGB", (width, height), hex_to_rgb(WARM_PAPER))
    draw = ImageDraw.Draw(img)

    font_title = load_editorial_font(size=int(26 * s))
    font_subtitle = load_font(bold=False, size=int(13 * s))
    font_time = load_font(bold=True, size=int(16 * s))
    font_label = load_font(bold=True, size=int(14 * s))
    font_detail = load_font(bold=False, size=int(12 * s))

    pad = int(40 * s)

    # Title — Source Serif 4 + gold rule
    draw.text((pad, int(14 * s)), "RACE-DAY FUELING TIMELINE",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.text((pad + int(420 * s), int(22 * s)), "Don't bonk. Fuel by the clock.",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_subtitle)
    rule_y = int(50 * s)
    draw_gold_rule(draw, pad, rule_y, width - pad, width=max(2, int(2 * s)))

    # Timeline bar
    n = len(MILESTONES)
    bar_y = int(220 * s)
    bar_h = int(8 * s)
    bar_left = pad + int(60 * s)
    bar_right = width - pad - int(60 * s)

    draw.rectangle([(bar_left, bar_y), (bar_right, bar_y + bar_h)],
                   fill=hex_to_rgb(PRIMARY_BROWN))

    # Milestone positions
    spacing = (bar_right - bar_left) / (n - 1)

    for i, ms in enumerate(MILESTONES):
        cx = int(bar_left + i * spacing)

        # Square marker on timeline (no circles — brand rule)
        r = int(14 * s)
        draw.rectangle([(cx - r, bar_y + bar_h // 2 - r),
                        (cx + r, bar_y + bar_h // 2 + r)],
                       fill=hex_to_rgb(DARK_TEAL),
                       outline=hex_to_rgb(DARK_BROWN), width=max(2, int(2 * s)))

        # Callout box ABOVE timeline
        box_w = int(160 * s)
        box_h = int(80 * s)
        box_x = cx - box_w // 2
        box_y = bar_y - int(140 * s)

        # Clamp to stay within image
        box_x = max(pad, min(box_x, width - pad - box_w))

        draw.rectangle([(box_x, box_y), (box_x + box_w, box_y + box_h)],
                       fill=hex_to_rgb(GOLD if i in (0, 3, 4) else WHITE),
                       outline=hex_to_rgb(DARK_BROWN), width=max(2, int(2 * s)))

        # Connector line from box to circle
        draw.line([(cx, box_y + box_h), (cx, bar_y + bar_h // 2 - r)],
                  fill=hex_to_rgb(DARK_BROWN), width=max(1, int(1 * s)))

        # Text in callout
        text_color = WHITE if i in (0, 3, 4) else NEAR_BLACK
        # Detail text (multi-line)
        lines = ms["detail"].split("\n")
        for j, line in enumerate(lines):
            draw.text((box_x + int(10 * s), box_y + int(8 * s) + j * int(18 * s)), line,
                      fill=hex_to_rgb(text_color), font=font_detail)

        # Time label BELOW timeline
        time_y = bar_y + bar_h + int(24 * s)
        bbox = draw.textbbox((0, 0), ms["time"], font=font_time)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, time_y), ms["time"],
                  fill=hex_to_rgb(DARK_TEAL), font=font_time)

        # Label below time
        label_y = time_y + int(24 * s)
        bbox = draw.textbbox((0, 0), ms["label"], font=font_label)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, label_y), ms["label"],
                  fill=hex_to_rgb(NEAR_BLACK), font=font_label)

    return img
