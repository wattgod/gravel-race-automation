"""Execution gap — plan vs reality interval comparison."""
from PIL import Image, ImageDraw

from .base import (
    load_font, hex_to_rgb,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, DARK_GOLD,
    GOLD, OFF_WHITE, BLACK, WHITE,
)

MUTED_TAN = "#c4b5ab"
RED = "#c0392b"
GREEN = "#178079"


def _draw_interval_chart(draw, x, y, w, h, intervals, title, title_color, font_title, font_label, font_sm):
    """Draw a set of intervals as bars."""
    # Title
    draw.text((x, y), title, fill=hex_to_rgb(title_color), font=font_title)

    bar_top = y + 35
    bar_h = h - 55
    num_intervals = len(intervals)
    gap = 12
    bar_w = (w - gap * (num_intervals - 1)) // num_intervals

    # Power axis reference: 250-350W range
    p_min, p_max = 240, 340
    p_range = p_max - p_min

    for i, (watts, duration_min, status) in enumerate(intervals):
        bx = x + i * (bar_w + gap)

        # Bar height proportional to watts
        fill_h = int(((watts - p_min) / p_range) * bar_h)
        fill_h = max(fill_h, 10)
        bar_bottom = bar_top + bar_h
        bar_y_top = bar_bottom - fill_h

        # Bar color based on status
        if status == "good":
            fill_color = DARK_TEAL
        elif status == "fade":
            fill_color = DARK_GOLD
        elif status == "fail":
            fill_color = RED
        else:
            fill_color = SECONDARY_BROWN

        # Draw bar
        draw.rectangle([(bx, bar_y_top), (bx + bar_w, bar_bottom)],
                       fill=hex_to_rgb(fill_color), outline=hex_to_rgb(BLACK), width=2)

        # Watts label above bar
        watt_text = f"{watts}W"
        bbox = draw.textbbox((0, 0), watt_text, font=font_label)
        tw = bbox[2] - bbox[0]
        draw.text((bx + (bar_w - tw) // 2, bar_y_top - 22),
                  watt_text, fill=hex_to_rgb(title_color), font=font_label)

        # Duration label below bar
        dur_text = f"{duration_min}min"
        bbox2 = draw.textbbox((0, 0), dur_text, font=font_sm)
        tw2 = bbox2[2] - bbox2[0]
        draw.text((bx + (bar_w - tw2) // 2, bar_bottom + 6),
                  dur_text, fill=hex_to_rgb(SECONDARY_BROWN), font=font_sm)

        # Failed X overlay
        if status == "fail":
            # Big X
            draw.line([(bx + 8, bar_y_top + 8), (bx + bar_w - 8, bar_bottom - 8)],
                      fill=hex_to_rgb(WHITE), width=4)
            draw.line([(bx + bar_w - 8, bar_y_top + 8), (bx + 8, bar_bottom - 8)],
                      fill=hex_to_rgb(WHITE), width=4)


def render(width: int = 1200, height: int = 600) -> Image.Image:
    """Render plan vs reality interval comparison."""
    img = Image.new("RGB", (width, height), hex_to_rgb(OFF_WHITE))
    draw = ImageDraw.Draw(img)

    font_title = load_font(bold=True, size=22)
    font_section = load_font(bold=True, size=18)
    font_label = load_font(bold=True, size=15)
    font_sm = load_font(bold=False, size=13)
    font_xs = load_font(bold=False, size=11)

    pad = 40

    # Title
    draw.text((pad, 18), "THE EXECUTION GAP", fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.text((pad + 310, 20), "Plan says: 3x15 min @ 95% FTP (300W)",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_sm)
    draw.line([(pad, 50), (width - pad, 50)], fill=hex_to_rgb(BLACK), width=2)

    half_w = (width - pad * 3) // 2
    chart_h = height - 180

    # Divider line
    mid_x = width // 2
    draw.line([(mid_x, 60), (mid_x, height - 100)], fill=hex_to_rgb(MUTED_TAN), width=2)

    # LEFT: Bad execution
    # intervals: (watts, duration, status)
    bad_intervals = [
        (320, 15, "fade"),    # Started too hot
        (290, 15, "fade"),    # Fading
        (270, 10, "fail"),    # Bailed at 10min
    ]
    _draw_interval_chart(draw, pad + 20, 65, half_w - 20, chart_h,
                         bad_intervals, "WRONG: CHASE WATTS", RED,
                         font_section, font_label, font_sm)

    # Bad annotation
    draw.text((pad + 20, height - 125),
              "Started 7% too hot. Faded every interval.",
              fill=hex_to_rgb(RED), font=font_sm)
    draw.text((pad + 20, height - 105),
              "Bailed at 10min on #3. Total time-in-zone: 28min",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

    # RIGHT: Good execution
    good_intervals = [
        (300, 15, "good"),
        (300, 15, "good"),
        (295, 15, "good"),
        (298, 15, "good"),
    ]
    _draw_interval_chart(draw, mid_x + 20, 65, half_w - 20, chart_h,
                         good_intervals, "RIGHT: CHASE TIME-IN-ZONE", GREEN,
                         font_section, font_label, font_sm)

    # Good annotation
    draw.text((mid_x + 20, height - 125),
              "Conservative start. Nailed all 4 intervals.",
              fill=hex_to_rgb(GREEN), font=font_sm)
    draw.text((mid_x + 20, height - 105),
              "Consistent power. Total time-in-zone: 60min",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

    # Bottom insight
    box_y = height - 75
    draw.rectangle([(pad, box_y), (width - pad, height - 18)],
                   fill=hex_to_rgb(WHITE), outline=hex_to_rgb(BLACK), width=2)
    draw.text((pad + 16, box_y + 8),
              "The athlete who executes 4x15min at 98% FTP gets more adaptation",
              fill=hex_to_rgb(BLACK), font=font_label)
    draw.text((pad + 16, box_y + 30),
              "than the one who does 1x15min at 107% FTP then blows up.",
              fill=hex_to_rgb(BLACK), font=font_label)

    # Source
    draw.text((pad, height - 14), "gravelgodcycling.com", fill=hex_to_rgb(MUTED_TAN), font=font_xs)

    return img
