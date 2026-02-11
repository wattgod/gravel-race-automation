"""Race week countdown — 7 daily cards from Monday to Sunday."""
from PIL import Image, ImageDraw

from .base import (
    load_font, hex_to_rgb,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL,
    DARK_GOLD, OFF_WHITE, BLACK, WHITE,
)

MUTED_TAN = "#c4b5ab"

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


def render(width: int = 1600, height: int = 600) -> Image.Image:
    """Render a 7-day race week countdown strip."""
    img = Image.new("RGB", (width, height), hex_to_rgb(OFF_WHITE))
    draw = ImageDraw.Draw(img)

    font_title = load_font(bold=True, size=22)
    font_subtitle = load_font(bold=False, size=13)
    font_day = load_font(bold=True, size=20)
    font_label = load_font(bold=True, size=12)
    font_task = load_font(bold=False, size=12)
    font_note = load_font(bold=False, size=11)
    font_xs = load_font(bold=False, size=11)

    pad = 30

    # Title
    draw.text((pad, 14), "RACE WEEK COUNTDOWN",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.text((pad + 340, 18), "Your fitness is locked in. This week is logistics.",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_subtitle)
    draw.line([(pad, 46), (width - pad, 46)], fill=hex_to_rgb(BLACK), width=2)

    # 7 columns
    n = len(DAYS)
    col_gap = 8
    total_gap = col_gap * (n - 1)
    col_w = (width - pad * 2 - total_gap) // n
    card_top = 62
    card_bottom = height - 36

    for i, day in enumerate(DAYS):
        x = pad + i * (col_w + col_gap)
        is_race_day = i == n - 1

        bg_color = DARK_TEAL if is_race_day else (WHITE if i % 2 == 0 else "#ede6dd")
        header_color = DARK_TEAL if is_race_day else (PRIMARY_BROWN if i % 2 == 0 else SECONDARY_BROWN)

        # Card background
        draw.rectangle([(x, card_top), (x + col_w, card_bottom)],
                       fill=hex_to_rgb(bg_color),
                       outline=hex_to_rgb(BLACK),
                       width=3 if is_race_day else 2)

        # Day header strip
        strip_h = 48
        draw.rectangle([(x, card_top), (x + col_w, card_top + strip_h)],
                       fill=hex_to_rgb(header_color))

        # Day name
        bbox = draw.textbbox((0, 0), day["day"], font=font_day)
        tw = bbox[2] - bbox[0]
        draw.text((x + (col_w - tw) // 2, card_top + 4),
                  day["day"], fill=hex_to_rgb(WHITE), font=font_day)

        # Sub-label
        bbox = draw.textbbox((0, 0), day["label"], font=font_label)
        tw = bbox[2] - bbox[0]
        draw.text((x + (col_w - tw) // 2, card_top + 28),
                  day["label"], fill=hex_to_rgb(WHITE), font=font_label)

        # Tasks
        task_y = card_top + strip_h + 16
        task_text_color = WHITE if is_race_day else BLACK

        draw.text((x + 10, task_y), "TASKS",
                  fill=hex_to_rgb(WHITE if is_race_day else header_color),
                  font=font_label)
        for j, task in enumerate(day["tasks"]):
            ty = task_y + 20 + j * 22
            # Truncate if needed for narrow columns
            draw.text((x + 10, ty), f"> {task}",
                      fill=hex_to_rgb(task_text_color), font=font_task)

        # Note at bottom
        note_y = card_bottom - 36
        draw.line([(x + 10, note_y - 6), (x + col_w - 10, note_y - 6)],
                  fill=hex_to_rgb(MUTED_TAN if not is_race_day else WHITE), width=1)
        draw.text((x + 10, note_y + 2), day["note"],
                  fill=hex_to_rgb(WHITE if is_race_day else SECONDARY_BROWN),
                  font=font_note)

    # Source
    draw.text((pad, height - 18), "gravelgodcycling.com",
              fill=hex_to_rgb(MUTED_TAN), font=font_xs)

    return img
