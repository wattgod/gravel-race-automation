"""Render an athlete's 2027 goal poster (docs/specs/goals-2027-funnel-spec.md, D8).

Drawn on demand from the answers stored on the enrollment, never written to
disk: Railway's filesystem does not survive a redeploy, so a file saved when
the lead arrived would 404 by the time the email is opened.

Brand: the D1 poster on the design canvas — near-black ground, Source Serif 4
for the goal, Sometype Mono for the frame, one teal rule. Same fonts the site
ships, loaded from guide/fonts/.
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from mission_control.config import REPO_ROOT

WIDTH, HEIGHT = 1080, 1440  # 3:4, prints at 12x16in

INK = (26, 22, 19)
PAPER = (245, 239, 230)
WHITE = (255, 255, 255)
TAN = (212, 197, 185)
TEAL = (23, 128, 121)
GOLD = (201, 169, 44)
GREY = (125, 105, 93)

_FONT_DIR = REPO_ROOT / "guide" / "fonts"
_FONTS = {
    "mono": _FONT_DIR / "SometypeMono-Regular.ttf",
    "mono_bold": _FONT_DIR / "SometypeMono-Bold.ttf",
    "serif": _FONT_DIR / "SourceSerif4-Variable.ttf",
}


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = _FONTS[name]
    if not path.exists():  # fonts ship with the repo; fall back rather than 500
        return ImageFont.load_default()
    font = ImageFont.truetype(str(path), size)
    if name == "serif":
        try:  # variable font: use the heaviest weight for the goal line
            font.set_variation_by_name("Black")
        except (AttributeError, OSError):
            pass
    return font


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        words, line = paragraph.split(), ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if draw.textlength(candidate, font=font) <= max_width or not line:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return [ln for ln in lines if ln]


def _fit(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_lines: int,
         sizes: tuple[int, ...]) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Largest size at which the goal still fits the space it is given."""
    font = _font("serif", sizes[-1])
    lines = _wrap(draw, text, font, max_width)
    for size in sizes:
        font = _font("serif", size)
        lines = _wrap(draw, text, font, max_width)
        if len(lines) <= max_lines:
            break
    return font, lines[:max_lines]


def _clean(value: str | None, limit: int = 160) -> str:
    return " ".join(str(value or "").split())[:limit]


def render_poster(answers: dict, name: str = "", season: int = 2027) -> bytes:
    """PNG bytes for one athlete's poster. Missing answers simply leave gaps.

    Laid out from the bottom up: the frame rows (the enemy, the plan, the
    habit) are anchored above the footer, and whatever room is left goes to
    the goal, which shrinks to fit rather than running over them.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), INK)
    draw = ImageDraw.Draw(img)
    pad = 84
    inner = WIDTH - pad * 2

    # header
    draw.text((pad, pad), f"{season} · GOAL FILE", font=_font("mono_bold", 26), fill=GOLD)
    draw.text((WIDTH - pad, pad), "GRAVEL GOD", font=_font("mono_bold", 26), fill=TAN, anchor="ra")
    draw.text((pad, HEIGHT - pad - 20), "GRAVELGODCYCLING.COM",
              font=_font("mono", 22), fill=GREY)

    # bottom block: the frame, anchored above the footer
    rows = [
        ("THE ENEMY", _clean(answers.get("inner_obstacle"), 150)),
        ("WHEN IT SHOWS UP", _clean(answers.get("obstacle_plan"), 150)),
        ("THE HABIT", _clean(answers.get("habit"), 150)),
        ("WHEN AND WHERE", _clean(answers.get("habit_when"), 150)),
    ]
    rows = [(k, v) for k, v in rows if v]
    label_font, value_font = _font("mono_bold", 24), _font("mono", 30)
    row_height = 96
    frame_top = HEIGHT - pad - 60 - len(rows) * row_height
    y = frame_top
    for key, value in rows:
        draw.text((pad, y), key, font=label_font, fill=TEAL)
        line = _wrap(draw, value, value_font, inner)[:1]
        if line:
            draw.text((pad, y + 34), line[0], font=value_font, fill=PAPER)
        y += row_height

    # middle block: the why, sitting just above the frame
    why = _clean(answers.get("outcome_why"), 200)
    why_font = _font("serif", 38)
    why_lines = _wrap(draw, f"\u201c{why}\u201d", why_font, inner)[:3] if why else []
    why_height = len(why_lines) * 50 + (30 if why_lines else 0)

    # top block: label, goal, rule — shrinks until it fits what's left
    label_y = pad + 300
    available = frame_top - why_height - label_y - 120
    goal = _clean(answers.get("outcome_goal"), 180) or "[your goal]"
    if not goal.endswith("."):
        goal += "."
    for size in (104, 92, 80, 68, 58, 48):
        goal_font = _font("serif", size)
        goal_lines = _wrap(draw, goal, goal_font, inner)
        line_height = int(size * 1.06)
        if len(goal_lines) * line_height <= available:
            break
    goal_lines = goal_lines[:6]

    who = _clean(name, 40).upper() or "I"
    draw.text((pad, label_y), f"BY THE END OF {season}, {who} WILL",
              font=_font("mono", 26), fill=TAN)
    y = label_y + 60
    for line in goal_lines:
        draw.text((pad, y), line, font=goal_font, fill=WHITE)
        y += line_height
    draw.rectangle([pad, y + 24, pad + 150, y + 30], fill=TEAL)

    # the why goes directly above the frame, never into it
    y = frame_top - why_height
    for line in why_lines:
        draw.text((pad, y), line, font=why_font, fill=TAN)
        y += 50

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
