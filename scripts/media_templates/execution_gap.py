"""Execution gap — plan vs reality interval comparison."""
from PIL import Image, ImageDraw

from .base import (
    load_font, load_editorial_font, hex_to_rgb, draw_gold_rule,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, GOLD,
    LIGHT_GOLD, WARM_PAPER, DARK_BROWN, NEAR_BLACK, WHITE, WARM_BROWN, ERROR_RED,
)

BASE_WIDTH = 1200


def _draw_interval_chart(draw, x, y, w, h, intervals, title, title_color, font_title, font_label, font_sm, s):
    """Draw a set of intervals as bars."""
    # Title
    draw.text((x, y), title, fill=hex_to_rgb(title_color), font=font_title)

    bar_top = y + int(35 * s)
    bar_h = h - int(55 * s)
    num_intervals = len(intervals)
    gap = int(12 * s)
    bar_w = (w - gap * (num_intervals - 1)) // num_intervals

    # Power axis reference: 250-350W range
    p_min, p_max = 240, 340
    p_range = p_max - p_min

    for i, (watts, duration_min, status) in enumerate(intervals):
        bx = x + i * (bar_w + gap)

        # Bar height proportional to watts
        fill_h = int(((watts - p_min) / p_range) * bar_h)
        fill_h = max(fill_h, int(10 * s))
        bar_bottom = bar_top + bar_h
        bar_y_top = bar_bottom - fill_h

        # Bar color based on status
        if status == "good":
            fill_color = DARK_TEAL
        elif status == "fade":
            fill_color = GOLD
        elif status == "fail":
            fill_color = ERROR_RED
        else:
            fill_color = SECONDARY_BROWN

        # Draw bar
        draw.rectangle([(bx, bar_y_top), (bx + bar_w, bar_bottom)],
                       fill=hex_to_rgb(fill_color), outline=hex_to_rgb(DARK_BROWN), width=max(2, int(2 * s)))

        # Watts label above bar
        watt_text = f"{watts}W"
        bbox = draw.textbbox((0, 0), watt_text, font=font_label)
        tw = bbox[2] - bbox[0]
        draw.text((bx + (bar_w - tw) // 2, bar_y_top - int(22 * s)),
                  watt_text, fill=hex_to_rgb(title_color), font=font_label)

        # Duration label below bar
        dur_text = f"{duration_min}min"
        bbox2 = draw.textbbox((0, 0), dur_text, font=font_sm)
        tw2 = bbox2[2] - bbox2[0]
        draw.text((bx + (bar_w - tw2) // 2, bar_bottom + int(6 * s)),
                  dur_text, fill=hex_to_rgb(SECONDARY_BROWN), font=font_sm)

        # Failed X overlay
        if status == "fail":
            # Big X
            draw.line([(bx + int(8 * s), bar_y_top + int(8 * s)),
                       (bx + bar_w - int(8 * s), bar_bottom - int(8 * s))],
                      fill=hex_to_rgb(WHITE), width=max(2, int(4 * s)))
            draw.line([(bx + bar_w - int(8 * s), bar_y_top + int(8 * s)),
                       (bx + int(8 * s), bar_bottom - int(8 * s))],
                      fill=hex_to_rgb(WHITE), width=max(2, int(4 * s)))


def render(width: int = 1200, height: int = 600) -> Image.Image:
    """Render plan vs reality interval comparison."""
    s = width / BASE_WIDTH

    img = Image.new("RGB", (width, height), hex_to_rgb(WARM_PAPER))
    draw = ImageDraw.Draw(img)

    font_title = load_editorial_font(size=int(26 * s))
    font_section = load_font(bold=True, size=int(18 * s))
    font_label = load_font(bold=True, size=int(15 * s))
    font_sm = load_font(bold=False, size=int(13 * s))
    font_xs = load_font(bold=False, size=int(11 * s))

    pad = int(40 * s)

    # Title — Source Serif 4 + gold rule
    draw.text((pad, int(14 * s)), "THE EXECUTION GAP", fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.text((pad + int(330 * s), int(22 * s)), "Plan says: 3x15 min @ 95% FTP (300W)",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_sm)
    rule_y = int(50 * s)
    draw_gold_rule(draw, pad, rule_y, width - pad, width=max(2, int(2 * s)))

    half_w = (width - pad * 3) // 2
    chart_h = height - int(180 * s)

    # Divider line
    mid_x = width // 2
    draw.line([(mid_x, int(60 * s)), (mid_x, height - int(100 * s))],
              fill=hex_to_rgb(WARM_BROWN), width=max(2, int(2 * s)))

    # LEFT: Bad execution
    # intervals: (watts, duration, status)
    bad_intervals = [
        (320, 15, "fade"),    # Started too hot
        (290, 15, "fade"),    # Fading
        (270, 10, "fail"),    # Bailed at 10min
    ]
    _draw_interval_chart(draw, pad + int(20 * s), int(65 * s), half_w - int(20 * s), chart_h,
                         bad_intervals, "WRONG: CHASE WATTS", ERROR_RED,
                         font_section, font_label, font_sm, s)

    # Bad annotation
    draw.text((pad + int(20 * s), height - int(125 * s)),
              "Started 7% too hot. Faded every interval.",
              fill=hex_to_rgb(ERROR_RED), font=font_sm)
    draw.text((pad + int(20 * s), height - int(105 * s)),
              "Bailed at 10min on #3. Total time-in-zone: 28min",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

    # RIGHT: Good execution
    good_intervals = [
        (300, 15, "good"),
        (300, 15, "good"),
        (295, 15, "good"),
        (298, 15, "good"),
    ]
    _draw_interval_chart(draw, mid_x + int(20 * s), int(65 * s), half_w - int(20 * s), chart_h,
                         good_intervals, "RIGHT: CHASE TIME-IN-ZONE", DARK_TEAL,
                         font_section, font_label, font_sm, s)

    # Good annotation
    draw.text((mid_x + int(20 * s), height - int(125 * s)),
              "Conservative start. Nailed all 4 intervals.",
              fill=hex_to_rgb(DARK_TEAL), font=font_sm)
    draw.text((mid_x + int(20 * s), height - int(105 * s)),
              "Consistent power. Total time-in-zone: 60min",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

    # Bottom insight
    box_y = height - int(75 * s)
    draw.rectangle([(pad, box_y), (width - pad, height - int(18 * s))],
                   fill=hex_to_rgb(WHITE), outline=hex_to_rgb(DARK_BROWN), width=max(2, int(2 * s)))
    draw.text((pad + int(16 * s), box_y + int(8 * s)),
              "The athlete who executes 4x15min at 98% FTP gets more adaptation",
              fill=hex_to_rgb(NEAR_BLACK), font=font_label)
    draw.text((pad + int(16 * s), box_y + int(30 * s)),
              "than the one who does 1x15min at 107% FTP then blows up.",
              fill=hex_to_rgb(NEAR_BLACK), font=font_label)

    return img
