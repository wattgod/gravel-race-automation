"""Scoring dimensions — 14 base criteria + cultural impact bonus in two columns with horizontal bars.

Loads Unbound Gravel 200 scores from race-data/ so the infographic stays
in sync with the database.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw

from .base import (
    load_font, load_editorial_font, hex_to_rgb, draw_gold_rule,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, GOLD,
    WARM_PAPER, DARK_BROWN, NEAR_BLACK, WHITE, WARM_BROWN, SAND,
)

RACE_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "race-data"

# Keys in biased_opinion_ratings → display labels, grouped by column
COURSE_KEYS = [
    ("length", "Length"),
    ("technicality", "Technicality"),
    ("elevation", "Elevation"),
    ("climate", "Climate"),
    ("altitude", "Altitude"),
    ("logistics", "Logistics"),
    ("adventure", "Adventure"),
]
EDITORIAL_KEYS = [
    ("prestige", "Prestige"),
    ("race_quality", "Race Quality"),
    ("experience", "Experience"),
    ("community", "Community"),
    ("field_depth", "Field Depth"),
    ("value", "Value"),
    ("expenses", "Expenses"),
]


def _load_unbound_scores() -> tuple[list, list, int]:
    """Load Unbound 200 scores from race data. Returns (course, editorial, overall)."""
    profile = RACE_DATA_DIR / "unbound-200.json"
    if not profile.exists():
        # Fallback to hardcoded if file missing (e.g. in test environments)
        return (
            [("Length", 5), ("Technicality", 3), ("Elevation", 3), ("Climate", 5),
             ("Altitude", 1), ("Logistics", 4), ("Adventure", 5)],
            [("Prestige", 5), ("Race Quality", 5), ("Experience", 5), ("Community", 5),
             ("Field Depth", 5), ("Value", 3), ("Expenses", 2)],
            80,
        )

    data = json.loads(profile.read_text(encoding="utf-8"))
    race = data.get("race", data)
    ratings = race.get("biased_opinion_ratings", {})
    overall = race.get("gravel_god_rating", {}).get("overall_score", 0)
    tier = race.get("gravel_god_rating", {}).get("display_tier", "?")

    course = [(label, ratings.get(key, {}).get("score", 0)) for key, label in COURSE_KEYS]
    editorial = [(label, ratings.get(key, {}).get("score", 0)) for key, label in EDITORIAL_KEYS]

    return course, editorial, overall, tier


def render(width: int = 1200, height: int = 800) -> Image.Image:
    """Render a two-column scoring dimensions chart."""
    s = width / 1200

    result = _load_unbound_scores()
    course, editorial, overall = result[0], result[1], result[2]
    tier = result[3] if len(result) > 3 else "?"

    img = Image.new("RGB", (width, height), hex_to_rgb(WARM_PAPER))
    draw = ImageDraw.Draw(img)

    font_title = load_editorial_font(size=int(26 * s))
    font_subtitle = load_font(bold=False, size=int(13 * s))
    font_col_head = load_font(bold=True, size=int(16 * s))
    font_label = load_font(bold=True, size=int(13 * s))
    font_score = load_font(bold=True, size=int(14 * s))
    font_xs = load_font(bold=False, size=int(11 * s))

    pad = int(40 * s)
    mid = width // 2

    # Title — Source Serif 4 + gold rule
    draw.text((pad, int(14 * s)), "15-DIMENSION SCORING SYSTEM",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.text((pad + int(440 * s), int(22 * s)), f"Example: Unbound Gravel (Score: {overall})",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_subtitle)
    rule_y = int(50 * s)
    draw_gold_rule(draw, pad, rule_y, width - pad, width=max(2, int(2 * s)))

    # Divider line
    draw.line([(mid, int(60 * s)), (mid, height - int(40 * s))],
              fill=hex_to_rgb(WARM_BROWN), width=max(1, int(1 * s)))

    def draw_column(dims, x_start, col_width, top_y, heading, bar_color):
        # Column heading
        draw.text((x_start, top_y), heading,
                  fill=hex_to_rgb(bar_color), font=font_col_head)
        draw.line([(x_start, top_y + int(24 * s)),
                   (x_start + col_width - int(20 * s), top_y + int(24 * s))],
                  fill=hex_to_rgb(DARK_BROWN), width=max(1, int(1 * s)))

        bar_top = top_y + int(38 * s)
        bar_h = int(28 * s)
        gap = int(12 * s)
        label_w = int(120 * s)
        bar_max_w = col_width - label_w - int(60 * s)

        for i, (name, score) in enumerate(dims):
            y = bar_top + i * (bar_h + gap)

            # Label
            draw.text((x_start, y + int(6 * s)), name,
                      fill=hex_to_rgb(NEAR_BLACK), font=font_label)

            # Bar background
            bx = x_start + label_w
            draw.rectangle([(bx, y), (bx + bar_max_w, y + bar_h)],
                           fill=hex_to_rgb(SAND), outline=hex_to_rgb(DARK_BROWN),
                           width=max(1, int(1 * s)))

            # Filled bar
            fill_w = int((score / 5) * bar_max_w)
            draw.rectangle([(bx, y), (bx + fill_w, y + bar_h)],
                           fill=hex_to_rgb(bar_color))

            # Score text
            draw.text((bx + bar_max_w + int(10 * s), y + int(5 * s)), f"{score}/5",
                      fill=hex_to_rgb(NEAR_BLACK), font=font_score)

    col_w = mid - pad - int(10 * s)
    col_top = int(64 * s)

    draw_column(course, pad, col_w, col_top,
                "COURSE DIMENSIONS", DARK_TEAL)
    draw_column(editorial, mid + int(10 * s), col_w, col_top,
                "EDITORIAL DIMENSIONS", GOLD)

    # Total score bar at bottom
    total_y = height - int(55 * s)
    draw.line([(pad, total_y - int(10 * s)), (width - pad, total_y - int(10 * s))],
              fill=hex_to_rgb(DARK_BROWN), width=max(2, int(2 * s)))
    draw.text((pad, total_y), f"OVERALL: {overall}/100 — TIER {tier}",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_col_head)
    return img
