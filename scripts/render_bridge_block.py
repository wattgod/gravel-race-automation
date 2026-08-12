#!/usr/bin/env python3
"""Render a light 10–14 day coaching bridge block as Markdown."""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mission_control.services.race_countdown import _fetch_dates_sync


DEFAULT_HOURS = 7.0

BLOCKS = {
    "comeback": {
        "days": 10,
        "intro": "The job is to make training feel normal again. Keep every aerobic day capped at RPE 4; finishing fresher than you started is the point.",
        "sessions": [
            ("Day 1", "Rest. A short walk is fine."),
            ("Day 2", "Easy aerobic ride — {easy} min at RPE 2–3."),
            ("Day 3", "Easy aerobic ride — {medium} min at RPE 3–4."),
            ("Day 4", "Rest. If symptoms or pain are moving backward, stop here."),
            ("Day 5", "Easy aerobic ride — {easy} min. Keep the pressure off the pedals."),
            ("Day 6", "Aerobic durability — {long} min at RPE 3–4. Eat and drink normally."),
            ("Day 7", "Recovery spin — {recovery} min, or take the day off."),
            ("Day 8", "Easy aerobic ride — {medium} min at RPE 3–4."),
            ("Day 9", "Rest."),
            ("Day 10", "Openers — {easy} min easy with 3 × 1 min at RPE 7, full easy riding between. Skip them if the body is not quiet."),
        ],
    },
    "base_hold": {
        "days": 14,
        "intro": "Nothing needs proving for two weeks. This is a quality-free durability block: steady frequency, one longer day each week, and rest before fatigue gets clever.",
        "sessions": [
            ("Day 1", "Rest."), ("Day 2", "Easy aerobic ride — {medium} min at RPE 3–4."),
            ("Day 3", "Easy spin — {recovery} min, or take the day off."),
            ("Day 4", "Steady aerobic ride — {medium} min at RPE 4."),
            ("Day 5", "Rest."), ("Day 6", "Durability ride — {long} min, all conversational."),
            ("Day 7", "Easy spin — {recovery} min."), ("Day 8", "Rest."),
            ("Day 9", "Easy aerobic ride — {medium} min at RPE 3–4."),
            ("Day 10", "Steady aerobic ride — {medium} min at RPE 4."),
            ("Day 11", "Rest or {recovery} min very easy."),
            ("Day 12", "Easy aerobic ride — {easy} min."),
            ("Day 13", "Durability ride — {long} min. Finish with something left."),
            ("Day 14", "Rest."),
        ],
    },
    "race_triage": {
        "days": 10,
        "intro": "Ten useful days beat ten desperate ones. There is one threshold touch, one long ride with race fuel, and no bonus work for confidence.",
        "sessions": [
            ("Day 1", "Rest."), ("Day 2", "Easy aerobic ride — {easy} min at RPE 3–4."),
            ("Day 3", "Threshold touch — {medium} min total with 3 × 6 min at RPE 7–8 and 4 min easy between."),
            ("Day 4", "Recovery spin — {recovery} min."), ("Day 5", "Rest."),
            ("Day 6", "Long ride — {long} min at endurance effort. Practice the exact race fuel and bottle timing."),
            ("Day 7", "Recovery spin — {recovery} min, or off."),
            ("Day 8", "Easy aerobic ride — {medium} min with 4 × 30 sec quick legs, not sprints."),
            ("Day 9", "Rest."), ("Day 10", "Easy ride — {easy} min. Finish wanting more."),
        ],
    },
}


def scaled_durations(hours: float | None) -> dict[str, int]:
    """Scale a 6–8 hour pattern conservatively; never turn low hours into a huge week."""
    weekly = DEFAULT_HOURS if hours is None else max(1.5, min(float(hours), 14.0))
    factor = weekly / DEFAULT_HOURS
    base = {"recovery": 30, "easy": 50, "medium": 75, "long": 150}
    return {key: max(20, int(round(minutes * factor / 5) * 5)) for key, minutes in base.items()}


def race_weeks_out(race: str, dates: dict[str, dict[str, str]], today: date | None = None) -> float | None:
    slugs = dates.get("gravelgod") or {}
    query = re.sub(r"[^a-z0-9]+", "-", race.casefold()).strip("-")
    match = query if query in slugs else next(iter(difflib.get_close_matches(query, slugs, n=1, cutoff=0.55)), None)
    if not match:
        return None
    return (date.fromisoformat(slugs[match]) - (today or date.today())).days / 7


def render_bridge_block(
    archetype: str,
    hours: float | None = None,
    race: str | None = None,
    dates: dict[str, dict[str, str]] | None = None,
    today: date | None = None,
) -> str:
    block = BLOCKS[archetype]
    duration = scaled_durations(hours)
    title = archetype.replace("_", " ").title()
    lines = [f"## {title} — {block['days']} days", "", block["intro"]]
    if hours is None:
        lines.extend(["", "This is built for roughly 6–8 hours a week. Adjust it to your life; do not make your life answer to the block."])
    else:
        lines.extend(["", f"Durations are scaled around a {hours:g}-hour week. Move a day when life needs it; keep the order of hard, easy, and rest."])

    if race:
        weeks = race_weeks_out(race, dates if dates is not None else _fetch_dates_sync(), today)
        if weeks is None:
            lines.extend(["", f"Race framing: I could not match {race} to a published date, so this block does not pretend to know the runway."])
        elif weeks < 6:
            lines.extend(["", f"Race framing: {race} is about {weeks:.0f} weeks out. Treat this as the last work block, then taper; do not repeat it."])
        elif weeks <= 10:
            lines.extend(["", f"Race framing: {race} is about {weeks:.0f} weeks out. This is triage, not a full build."])
        else:
            lines.extend(["", f"Race framing: {race} is about {weeks:.0f} weeks out. There is no reason to force race work into these ten days."])

    lines.extend(["", "### The block", ""])
    for label, session in block["sessions"]:
        lines.append(f"- **{label}:** {session.format(**duration)}")
    lines.extend(["", "If you do it, tell me how it felt — that's the whole price."])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archetype", choices=sorted(BLOCKS), required=True)
    parser.add_argument("--race")
    parser.add_argument("--hours", type=float)
    args = parser.parse_args()
    print(render_bridge_block(args.archetype, args.hours, args.race))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
