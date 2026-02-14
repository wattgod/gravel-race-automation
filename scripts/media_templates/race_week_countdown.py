"""Race week countdown — 7 daily cards from Monday to Sunday."""
from PIL import Image, ImageDraw

from .base import (
    load_font, load_editorial_font, hex_to_rgb, draw_gold_rule,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL,
    GOLD, WARM_BROWN, SAND, WARM_PAPER, DARK_BROWN, NEAR_BLACK, WHITE,
)

DAYS = [
    {
        "day": "MON",
        "label": "7 Days Out",
        "tasks": ["60-90 min Z2", "3x1 min Z4 openers"],
        "note": "Keep legs moving",
    },
    {
        "day": "TUE",
        "label": "6 Days Out",
        "tasks": ["45-60 min Z2", "2x3 min G Spot opt."],
        "note": "Don't go hard",
    },
    {
        "day": "WED",
        "label": "5 Days Out",
        "tasks": ["Rest or 30 min spin", "Sleep 8-9 hrs"],
        "note": "Recovery priority",
    },
    {
        "day": "THU",
        "label": "4 Days Out",
        "tasks": ["45-60 min Z2", "3-5x30s Z5 openers"],
        "note": "Last real ride",
    },
    {
        "day": "FRI",
        "label": "3 Days Out",
        "tasks": ["Travel / rest day", "Bike check + pack"],
        "note": "Logistics day",
    },
    {
        "day": "SAT",
        "label": "2 Days Out",
        "tasks": ["30-45 min Z2", "3x1 min Z4 openers"],
        "note": "Course preview opt.",
    },
    {
        "day": "SUN",
        "label": "RACE DAY",
        "tasks": ["Wake 3hrs early", "100-150g carbs bkfst"],
        "note": "Execute the plan",
    },
]

BASE_WIDTH = 1600


def render(width: int = 1600, height: int = 600) -> Image.Image:
    """Render a 7-day race week countdown strip."""
    s = width / BASE_WIDTH

    img = Image.new("RGB", (width, height), hex_to_rgb(WARM_PAPER))
    draw = ImageDraw.Draw(img)

    font_title = load_editorial_font(size=int(26 * s))
    font_subtitle = load_font(bold=False, size=int(13 * s))
    font_day = load_font(bold=True, size=int(20 * s))
    font_label = load_font(bold=True, size=int(12 * s))
    font_task = load_font(bold=False, size=int(12 * s))
    font_note = load_font(bold=False, size=int(11 * s))

    pad = int(30 * s)

    # Title — Source Serif 4 + gold rule
    draw.text((pad, int(10 * s)), "RACE WEEK COUNTDOWN",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.text((pad + int(360 * s), int(18 * s)),
              "Your fitness is locked in. This week is logistics.",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_subtitle)
    rule_y = int(46 * s)
    draw_gold_rule(draw, pad, rule_y, width - pad, width=max(2, int(2 * s)))

    # 7 columns
    n = len(DAYS)
    col_gap = int(8 * s)
    total_gap = col_gap * (n - 1)
    col_w = (width - pad * 2 - total_gap) // n
    card_top = int(62 * s)
    card_bottom = height - int(36 * s)

    for i, day in enumerate(DAYS):
        x = pad + i * (col_w + col_gap)
        is_race_day = i == n - 1

        bg_color = DARK_TEAL if is_race_day else (WHITE if i % 2 == 0 else SAND)
        header_color = DARK_TEAL if is_race_day else (PRIMARY_BROWN if i % 2 == 0 else SECONDARY_BROWN)

        # Card background
        draw.rectangle([(x, card_top), (x + col_w, card_bottom)],
                       fill=hex_to_rgb(bg_color),
                       outline=hex_to_rgb(DARK_BROWN),
                       width=max(3, int(3 * s)) if is_race_day else max(2, int(2 * s)))

        # Day header strip
        strip_h = int(48 * s)
        draw.rectangle([(x, card_top), (x + col_w, card_top + strip_h)],
                       fill=hex_to_rgb(header_color))

        # Day name
        bbox = draw.textbbox((0, 0), day["day"], font=font_day)
        tw = bbox[2] - bbox[0]
        draw.text((x + (col_w - tw) // 2, card_top + int(4 * s)),
                  day["day"], fill=hex_to_rgb(WHITE), font=font_day)

        # Sub-label
        bbox = draw.textbbox((0, 0), day["label"], font=font_label)
        tw = bbox[2] - bbox[0]
        draw.text((x + (col_w - tw) // 2, card_top + int(28 * s)),
                  day["label"], fill=hex_to_rgb(WHITE), font=font_label)

        # Tasks
        task_y = card_top + strip_h + int(16 * s)
        task_text_color = WHITE if is_race_day else NEAR_BLACK

        draw.text((x + int(10 * s), task_y), "TASKS",
                  fill=hex_to_rgb(WHITE if is_race_day else header_color),
                  font=font_label)
        for j, task in enumerate(day["tasks"]):
            ty = task_y + int(20 * s) + j * int(22 * s)
            # Truncate if needed for narrow columns
            draw.text((x + int(10 * s), ty), f"> {task}",
                      fill=hex_to_rgb(task_text_color), font=font_task)

        # Note at bottom
        note_y = card_bottom - int(36 * s)
        draw.line([(x + int(10 * s), note_y - int(6 * s)),
                   (x + col_w - int(10 * s), note_y - int(6 * s))],
                  fill=hex_to_rgb(WARM_BROWN if not is_race_day else WHITE),
                  width=max(1, int(1 * s)))
        draw.text((x + int(10 * s), note_y + int(2 * s)), day["note"],
                  fill=hex_to_rgb(WHITE if is_race_day else SECONDARY_BROWN),
                  font=font_note)

    return img
