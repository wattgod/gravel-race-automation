#!/usr/bin/env python3
"""
Auto-draft the weekly Gravel TV desk note.

Runs in CI every week so the broadcast never depends on anyone
remembering to write it. The coach can still overwrite the file by hand
any week — manual edits committed after the draft simply win at deploy.

Guardrails (this is auto-published editorial, so the leash is short):
  - The model receives ONLY facts from the race database and may not
    invent results, quotes, or claims (system prompt + audit below)
  - Output runs through slop_rules.check_text — any banned phrase kills
    the draft
  - Any failure (API, gate, length) falls back to a plain data-driven
    note that contains nothing a database query didn't say

Usage:
    ANTHROPIC_API_KEY=... python3 scripts/draft_desk_note.py
    python3 scripts/draft_desk_note.py --fallback-only   # no API call
"""

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'wordpress'))
sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))

from generate_gravel_tv import load_races  # noqa: E402  (reuses date parser)
from slop_rules import check_text  # noqa: E402

DESK_NOTE = PROJECT_ROOT / 'web' / 'gravel-tv-desk-note.md'

VOICE_CARD = """You write the weekly desk note for GRAVEL TV in the voice of
Matti Rowe — cyclist, coach, race critic. Voice rules:
- Direct, dry, a little irreverent. Treats the reader as an adult.
- Specificity over superlatives. Named races, real dates, real tiers.
- No marketing language. No 'epic', no 'unleash', no 'journey'.
- One or two parenthetical asides maximum.
- 120-200 words. Three short paragraphs at most.
- End on something concrete, not a summary or exhortation.
HARD CONSTRAINTS:
- Use ONLY the facts in the provided data. Do not invent results, rider
  names, weather, history, or anything not literally present.
- If the calendar is thin, say so plainly — do not pad."""


def gather_facts(today: date) -> dict:
    races = load_races()
    horizon = today + timedelta(days=14)
    upcoming = sorted(
        ({'name': r['name'], 'date': r['date'].isoformat(),
          'tier': r['tier'], 'discipline': r['discipline'],
          'location': r['location']}
         for r in races if r['date'] and today <= r['date'] <= horizon),
        key=lambda r: (r['date'], r['tier'] or 9))
    return {
        'week_of': today.isoformat(),
        'upcoming_races': upcoming[:20],
        'tier1_count': sum(1 for r in upcoming if r['tier'] == 1),
        'total_upcoming': len(upcoming),
    }


def fallback_note(facts: dict) -> str:
    """A note that contains nothing a database query didn't say."""
    n = facts['total_upcoming']
    t1 = facts['tier1_count']
    leads = [r for r in facts['upcoming_races'] if r['tier'] in (1, 2)][:3]
    lines = [f"# Desk Note — week of {facts['week_of']}", ""]
    if n == 0:
        lines.append("Quiet stretch on the calendar this week. "
                     "Use it — the season never stays quiet for long.")
    else:
        lines.append(
            f"{n} races on the calendar in the next two weeks"
            + (f", including {t1} Tier 1{'s' if t1 != 1 else ''}" if t1 else "")
            + ".")
        if leads:
            picks = '; '.join(f"{r['name']} ({r['date']})" for r in leads)
            lines.append("")
            lines.append(f"The desk's watch list: {picks}.")
    lines.append("")
    lines.append("Full rundown below. New broadcast every week.")
    return '\n'.join(lines) + '\n'


def draft_with_claude(facts: dict) -> str | None:
    try:
        import anthropic
    except ImportError:
        print("anthropic SDK not installed — using fallback")
        return None
    try:
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=VOICE_CARD,
            messages=[{
                "role": "user",
                "content": (
                    "Write this week's desk note from these facts only:\n\n"
                    + json.dumps(facts, indent=2)
                ),
            }],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        print(f"Claude draft failed ({e}) — using fallback")
        return None


def gate(note: str, facts: dict) -> tuple[bool, str]:
    """Validate a drafted note. Returns (ok, reason)."""
    words = len(note.split())
    if not 60 <= words <= 280:
        return False, f"length out of bounds ({words} words)"
    violations = check_text(note)
    if violations:
        return False, f"slop: {[v['phrase'] for v in violations]}"
    # Race names mentioned must exist in the provided facts (anti-invention)
    known = {r['name'] for r in facts['upcoming_races']}
    for m in re.finditer(r'\b((?:[A-Z][\w\'-]+\s){1,4}(?:Gravel|Fondo|GRVL|200|100))\b', note):
        candidate = m.group(1).strip()
        if candidate and not any(candidate.lower() in k.lower() or k.lower() in candidate.lower()
                                 for k in known):
            return False, f"possible invented race name: {candidate!r}"
    return True, "ok"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fallback-only', action='store_true',
                        help='Skip the API; write the data-only note')
    args = parser.parse_args()

    today = date.today()
    facts = gather_facts(today)

    note = None
    if not args.fallback_only:
        draft = draft_with_claude(facts)
        if draft:
            ok, reason = gate(draft, facts)
            if ok:
                note = f"# Desk Note — week of {facts['week_of']}\n\n{draft}\n"
                print("Claude draft passed gates")
            else:
                print(f"Draft rejected ({reason}) — using fallback")

    if note is None:
        note = fallback_note(facts)
        print("Using data-only fallback note")

    DESK_NOTE.write_text(note)
    print(f"Wrote {DESK_NOTE} ({len(note)} chars)")
    print("-" * 50)
    print(note)
    return 0


if __name__ == '__main__':
    sys.exit(main())
