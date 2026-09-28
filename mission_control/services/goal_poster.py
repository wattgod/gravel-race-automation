"""Render an athlete's 2027 goal poster (docs/specs/goals-2027-funnel-spec.md, D8).

Drawn on demand from the answers stored on the enrollment, never written to
disk: Railway's filesystem does not survive a redeploy, so a file saved when
the lead arrived would 404 by the time the email is opened.

Brand: the paper poster (Matti, Sep 23: paper over dark) — warm paper ground,
near-black ink, Source Serif 4 for the goal, Sometype Mono for the frame, one
accent rule. Same fonts every brand ships, loaded from guide/fonts/. Layout,
copy and fonts are shared across brands; only the four colors, the
corner mark and the footer domain change (BRANDS below). Unknown or
unpassed brand renders as Gravel God (pre-multi-brand behavior, unchanged).
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from mission_control.config import REPO_ROOT

WIDTH, HEIGHT = 1080, 1440  # 3:4, prints at 12x16in

# Back-compat module-level constants (some callers/tests reference these
# directly) — always the Gravel God values, i.e. BRANDS["gravelgod"].
INK = (26, 22, 19)
PAPER = (245, 239, 230)
TEAL = (23, 128, 121)
GREY = (125, 105, 93)

BRANDS = {
    "gravelgod": {
        "ink": INK, "paper": PAPER, "accent": TEAL, "grey": GREY,
        "mark": "GRAVEL GOD", "domain": "GRAVELGODCYCLING.COM",
    },
    # XC Ski Labs — vintage Nordic-print tokens (tokens/tokens.css in the
    # xc-ski-labs repo): --gl-ink, --gl-paper, --gl-rust (spot accent),
    # --gl-caption. Same two font families as every other brand's poster.
    "xcskilabs": {
        "ink": (32, 40, 34), "paper": (240, 232, 216),
        "accent": (168, 61, 45), "grey": (97, 93, 81),
        "mark": "XC SKI LABS", "domain": "XCSKILABS.COM",
    },
}


def _brand(brand: str) -> dict:
    return BRANDS.get(brand, BRANDS["gravelgod"])


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


def render_poster(answers: dict, name: str = "", season: int | str = 2027,
                   brand: str = "gravelgod") -> bytes:
    """PNG bytes for one athlete's poster. Missing answers simply leave gaps.

    Laid out from the bottom up: the frame rows (the enemy, the plan, the
    habit) are anchored above the footer, and whatever room is left goes to
    the goal, which shrinks to fit rather than running over them.

    `brand` picks the four colors and the corner mark/footer domain from
    BRANDS; everything else (layout, fonts, copy) is identical across brands.
    """
    b = _brand(brand)
    ink, paper, accent, grey = b["ink"], b["paper"], b["accent"], b["grey"]
    img = Image.new("RGB", (WIDTH, HEIGHT), paper)
    draw = ImageDraw.Draw(img)
    pad = 84
    inner = WIDTH - pad * 2

    # header
    draw.text((pad, pad), f"{season} · GOAL FILE", font=_font("mono_bold", 26), fill=accent)
    draw.text((WIDTH - pad, pad), b["mark"], font=_font("mono_bold", 26), fill=ink, anchor="ra")
    draw.text((pad, HEIGHT - pad - 20), b["domain"],
              font=_font("mono", 22), fill=grey)

    # bottom block: the daily habits and the thing most likely to wreck it,
    # anchored above the footer (Matti, Sep 23)
    habit = _clean(answers.get("habit"), 120)
    if habit and answers.get("habit_when"):
        habit += " \u2014 " + _clean(answers.get("habit_when"), 120)
    value_font = _font("mono", 30)
    rows = [
        ("STOPPING" if answers.get("habit_direction") == "reduce" else "EVERY DAY", habit),
        ("ALSO EVERY DAY", _clean(answers.get("habit_2"), 150)),
        ("WATCH FOR", _clean(answers.get("inner_obstacle"), 150)),
    ]
    rows = [(k, _wrap(draw, v, value_font, inner)[:2]) for k, v in rows if v]
    label_font = _font("mono_bold", 24)
    frame_top = HEIGHT - pad - 60 - sum(56 + len(lines) * 38 for _, lines in rows)
    y = frame_top
    for key, lines in rows:
        draw.text((pad, y), key, font=label_font, fill=accent)
        for i, line in enumerate(lines):
            draw.text((pad, y + 34 + i * 38), line, font=value_font, fill=ink)
        y += 56 + len(lines) * 38

    # middle block: the deepest why they gave, just above the frame
    deepest = next((answers.get(k) for k in ("why_5", "why_4", "why_3", "why_2", "outcome_why")
                    if str(answers.get(k) or "").strip()), "")
    why = _clean(deepest, 200)
    why_font = _font("serif", 38)
    why_lines = _wrap(draw, f"\u201c{why}\u201d", why_font, inner)[:3] if why else []
    why_height = len(why_lines) * 50 + (30 if why_lines else 0)

    # top block: label, goal, rule — shrinks until it fits what's left
    label_y = pad + 200
    available = frame_top - why_height - label_y - 120
    goal = _clean(answers.get("outcome_goal"), 180) or "[your goal]"
    if goal[-1] not in ".!?":
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
              font=_font("mono", 26), fill=grey)
    y = label_y + 60
    for line in goal_lines:
        draw.text((pad, y), line, font=goal_font, fill=ink)
        y += line_height
    draw.rectangle([pad, y + 24, pad + 150, y + 30], fill=accent)

    # the why goes directly above the frame, never into it
    y = frame_top - why_height
    for line in why_lines:
        draw.text((pad, y), line, font=why_font, fill=grey)
        y += 50

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
