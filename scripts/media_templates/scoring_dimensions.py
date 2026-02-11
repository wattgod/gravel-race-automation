"""Scoring dimensions — 14 criteria in two columns with horizontal bars.

Loads Unbound Gravel 200 scores from race-data/ so the infographic stays
in sync with the database.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw

from .base import (
    load_font, hex_to_rgb,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, DARK_GOLD,
    OFF_WHITE, BLACK, WHITE,
)

MUTED_TAN = "#c4b5ab"

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
    result = _load_unbound_scores()
    course, editorial, overall = result[0], result[1], result[2]
    tier = result[3] if len(result) > 3 else "?"

    img = Image.new("RGB", (width, height), hex_to_rgb(OFF_WHITE))
    draw = ImageDraw.Draw(img)

    font_title = load_font(bold=True, size=22)
    font_subtitle = load_font(bold=False, size=13)
    font_col_head = load_font(bold=True, size=16)
    font_label = load_font(bold=True, size=13)
    font_score = load_font(bold=True, size=14)
    font_xs = load_font(bold=False, size=11)

    pad = 40
    mid = width // 2

    # Title
    draw.text((pad, 16), "14-DIMENSION SCORING SYSTEM",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.text((pad + 420, 20), f"Example: Unbound Gravel (Score: {overall})",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_subtitle)
    draw.line([(pad, 48), (width - pad, 48)], fill=hex_to_rgb(BLACK), width=2)

    # Divider line
    draw.line([(mid, 60), (mid, height - 40)], fill=hex_to_rgb(MUTED_TAN), width=1)

    def draw_column(dims, x_start, col_width, top_y, heading, bar_color):
        # Column heading
        draw.text((x_start, top_y), heading,
                  fill=hex_to_rgb(bar_color), font=font_col_head)
        draw.line([(x_start, top_y + 24), (x_start + col_width - 20, top_y + 24)],
                  fill=hex_to_rgb(BLACK), width=1)

        bar_top = top_y + 38
        bar_h = 28
        gap = 12
        label_w = 120
        bar_max_w = col_width - label_w - 60

        for i, (name, score) in enumerate(dims):
            y = bar_top + i * (bar_h + gap)

            # Label
            draw.text((x_start, y + 6), name,
                      fill=hex_to_rgb(BLACK), font=font_label)

            # Bar background
            bx = x_start + label_w
            draw.rectangle([(bx, y), (bx + bar_max_w, y + bar_h)],
                           fill=hex_to_rgb("#e8e0d8"), outline=hex_to_rgb(BLACK), width=1)

            # Filled bar
            fill_w = int((score / 5) * bar_max_w)
            draw.rectangle([(bx, y), (bx + fill_w, y + bar_h)],
                           fill=hex_to_rgb(bar_color))

            # Score text
            draw.text((bx + bar_max_w + 10, y + 5), f"{score}/5",
                      fill=hex_to_rgb(BLACK), font=font_score)

    col_w = mid - pad - 10
    col_top = 64

    draw_column(course, pad, col_w, col_top,
                "COURSE DIMENSIONS", DARK_TEAL)
    draw_column(editorial, mid + 10, col_w, col_top,
                "EDITORIAL DIMENSIONS", DARK_GOLD)

    # Total score bar at bottom
    total_y = height - 55
    draw.line([(pad, total_y - 10), (width - pad, total_y - 10)],
              fill=hex_to_rgb(BLACK), width=2)
    draw.text((pad, total_y), f"OVERALL: {overall}/100 — TIER {tier}",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_col_head)
    draw.text((width - pad - 200, total_y), "gravelgodcycling.com",
              fill=hex_to_rgb(MUTED_TAN), font=font_xs)

    return img
