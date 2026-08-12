#!/usr/bin/env python3
"""Draft Matti's reply to a "here's my race" email in ~2 seconds.

Both welcome sequences promise: "reply with your race and I'll give you my
honest read on what your remaining weeks are best spent doing." Those replies
are the warmest leads in the funnel — this tool makes answering one take 30
seconds instead of 10 minutes, without sounding canned: the FACTS dominate
(real date, real weeks, real course character from the profile), and the
frame is picked by runway bucket, each honest for its window.

Usage:
    python3 scripts/draft_race_reply.py "SBT GRVL"
    python3 scripts/draft_race_reply.py "mallorca 312" --brand road --name Jen
    python3 scripts/draft_race_reply.py unbound-200 --copy      # → clipboard

Output: a draft reply to paste into Gmail. Edit before sending — this is a
starting point in the right voice with the right numbers, not an autoresponder.
"""

from __future__ import annotations

import argparse
import difflib
import html
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

GRAVEL_ROOT = Path(__file__).resolve().parent.parent
ROAD_ROOT = GRAVEL_ROOT.parent / "road-race-automation"

sys.path.insert(0, str(GRAVEL_ROOT / "scripts"))
from generate_race_dates import parse_date_specific  # noqa: E402

BRANDS = {
    "gravel": {"root": GRAVEL_ROOT, "site": "https://gravelgodcycling.com",
               "plans_url": "https://gravelgodcycling.com/products/training-plans/"},
    "road": {"root": ROAD_ROOT, "site": "https://roadielabs.com",
             "plans_url": "https://roadielabs.com/training-plans/"},
}

# Debrief labels are evaluated in this order.  The first match is primary,
# while every match is retained so a reply such as "DNS after the knee flared"
# does not lose either part of the story.
DEBRIEF_PRIORITY = (
    "illness", "injury", "fueling", "pacing", "mechanical",
    "dns_deferred", "logistics", "happy",
)

DEBRIEF_KEYWORDS = {
    "illness": (r"\bsick\b", r"\bill(?:ness)?\b", r"\bcovid\b", r"\bflu\b", r"\bvirus\b", r"\bfever\b"),
    "injury": (r"\binjur(?:y|ed)\b", r"\bknee\b", r"\bback pain\b", r"\bpt\b", r"physical therap", r"\bfit issue\b"),
    "fueling": (r"\bfuel(?:ing|led)?\b", r"\bnutrition\b", r"\bbonk(?:ed|ing)?\b", r"\bcarbs?\b", r"\bgels?\b"),
    "pacing": (r"\bpac(?:e|ed|ing)\b", r"\btoo hard\b", r"\btoo fast\b", r"\bblew up\b", r"\bback half\b"),
    "mechanical": (r"\bmechanical\b", r"\bflat tire\b", r"\bpuncture\b", r"\bchain\b", r"\bderailleur\b", r"\bbroke(?:n)?\b"),
    "dns_deferred": (r"\bdns\b", r"did not start", r"didn't start", r"\bdefer(?:red|ral)?\b", r"\bwithdrew\b"),
    "logistics": (r"\blogistics?\b", r"\btravel\b", r"\bflight\b", r"\bhotel\b", r"\bregistration\b", r"\bstart time\b"),
    "happy": (r"\bhappy\b", r"\bpr\b", r"personal best", r"\bnailed\b", r"\bgreat day\b", r"\bwent well\b"),
}

DEBRIEF_QUESTIONS = {
    "illness": "What did your biggest week look like before you got sick?",
    "injury": "What has the PT or bike-fit work not resolved yet?",
    "fueling": "What did you eat and drink in the two hours before it started going wrong?",
    "pacing": "Where did the effort first stop feeling sustainable?",
    "mechanical": "Was it bad luck, or is there something in the setup you would change before the next one?",
    "dns_deferred": "Do you have another race in mind, or is the next move getting healthy first?",
    "logistics": "Which part of the day was still uncertain when you got to the start?",
    "happy": "What do you think made the biggest difference?",
    "unknown": "What part of the day do you most want to understand?",
}


def find_race(query: str, root: Path) -> Path | None:
    """Fuzzy-match a race name/slug against race-data/*.json."""
    data_dir = root / "race-data"
    slugs = {p.stem: p for p in data_dir.glob("*.json")}
    q = query.lower().strip().replace(" ", "-")
    if q in slugs:
        return slugs[q]
    # fuzzy on slug, then on race name
    close = difflib.get_close_matches(q, slugs.keys(), n=1, cutoff=0.6)
    if close:
        return slugs[close[0]]
    names = {}
    for slug, p in slugs.items():
        try:
            names[json.loads(p.read_text())["race"]["name"].lower()] = p
        except Exception:
            continue
    close = difflib.get_close_matches(query.lower(), names.keys(), n=1, cutoff=0.5)
    return names[close[0]] if close else None


def race_facts(path: Path, site: str) -> dict:
    d = json.loads(path.read_text())["race"]
    vitals = d.get("vitals") or {}
    rating = d.get("gravel_god_rating") or d.get("fondo_rating") or {}
    iso = parse_date_specific(vitals.get("date_specific"))
    weeks = None
    if iso:
        weeks = (date.fromisoformat(iso) - date.today()).days / 7
    return {
        "name": d.get("name", path.stem),
        "slug": path.stem,
        "url": f"{site}/race/{path.stem}/",
        "date_iso": iso,
        "date_text": vitals.get("date_specific") or vitals.get("date") or "date TBD",
        "weeks_out": weeks,
        "distance": vitals.get("distance_mi"),
        "elevation": vitals.get("elevation_ft"),
        "score": rating.get("overall_score"),
        "tier": rating.get("tier"),
    }


def draft(f: dict, first_name: str, plans_url: str) -> str:
    """Pick the honest frame for the runway bucket and assemble the reply."""
    hi = f"{first_name} —" if first_name else "Hey —"
    stats = []
    if f["distance"]:
        stats.append(f"{f['distance']:.0f} miles")
    if f["elevation"]:
        stats.append(f"{f['elevation']:,.0f} ft of climbing")
    stat_line = " and ".join(stats)
    w = f["weeks_out"]

    if w is None:
        body = f"""Good choice digging into {f['name']} — the full profile is here:
{f['url']}

I don't have a confirmed {date.today().year} date for it yet, so the honest runway math
will have to wait until the organizers commit. Reply once you're registered and I'll
tell you exactly what your weeks are best spent on."""
    elif w < 0:
        body = f"""{f['name']} already ran this year — so either congratulations or
condolences, and I'd genuinely like to know which. If you're picking the next one,
the database is the place to argue with me:
{f['url']}"""
    elif w < 5:
        body = f"""{f['name']} is about {w:.0f} weeks out{' — ' + stat_line if stat_line else ''}.

Straight answer: that's too short a runway for a training plan to change much, and I'd
rather tell you that than sell you one. What those weeks ARE for: keep the legs moving,
practice your race-day fueling on every long ride, make a pacing plan from the course
profile, and taper properly the last 10 days. All of that is on the race page, free:
{f['url']}

Reply after the race and tell me how it went — if there's a next one on the calendar,
that's when a plan is worth your money."""
    elif w <= 10:
        body = f"""{f['name']} is about {w:.0f} weeks out{' — ' + stat_line if stat_line else ''}.

That's a real but short runway. Honest read: the base-building window is mostly gone,
so the job now is sharpening what you have — race-specific intensity, pacing that
matches the course, and fueling you've practiced instead of improvised. Start with
the course section here and read it twice:
{f['url']}

If you want the structured version — every remaining week built from the course
profile, your FTP, and your real schedule, rebuilt by reply when life interferes —
that's what I sell, and {w:.0f} weeks is still worth structuring: {plans_url}
Under about five weeks I'd have told you to keep your money."""
    else:
        body = f"""{f['name']} is about {w:.0f} weeks out{' — ' + stat_line if stat_line else ''}.

That's the full window — the last stretch where a plan gets to use every kind of week
it needs, including the long unglamorous base work everything sharper stands on. Two
things to do this week regardless of whether you buy anything from me: read the course
section of the profile twice (the second read is where your pacing plan comes from),
and start practicing race-day fueling on your long rides now, not in September.
{f['url']}

If you want it built for you — every workout from now to the start line, from the
actual course profile and your real schedule, delivered in 48 hours: {plans_url}
Either way, you picked a good one."""

    return f"{hi}\n\n{body}\n\n— Matti"


def clean_reply_text(raw: str) -> str:
    """Return the athlete-authored portion as plain, compact text."""
    text = re.sub(r"(?is)<(blockquote|style|script)\b.*?</\1>", " ", raw or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">") or re.match(r"(?i)^on .+ wrote:$", stripped):
            break
        if stripped:
            kept.append(stripped)
    return re.sub(r"\s+", " ", " ".join(kept)).strip()


def classify_debrief(reply_text: str) -> dict:
    """Deterministically classify a debrief reply; multiple labels may match."""
    cleaned = clean_reply_text(reply_text)
    folded = cleaned.casefold()
    labels = [
        label for label in DEBRIEF_PRIORITY
        if any(re.search(pattern, folded) for pattern in DEBRIEF_KEYWORDS[label])
    ]
    return {"primary": labels[0] if labels else "unknown", "labels": labels, "text": cleaned}


def _specific_fragment(cleaned: str) -> str:
    if not cleaned:
        return "I couldn't pull a clean sentence out of your reply"
    fragment = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)[0].strip()
    if len(fragment) > 150:
        fragment = fragment[:147].rsplit(" ", 1)[0] + "…"
    return f'“{fragment}”'


def draft_debrief(reply_text: str, first_name: str = "", facts: dict | None = None) -> str:
    """Draft a reply that acknowledges, diagnoses, and only then offers help."""
    result = classify_debrief(reply_text)
    primary = result["primary"]
    hi = f"{first_name} —" if first_name else "Hey —"
    fragment = _specific_fragment(result["text"])

    if primary == "illness":
        read = "Getting interrupted by illness is solvable, but the order matters — rebuild aerobically before you touch intensity."
    elif primary == "injury":
        read = "That sounds like a return-to-training problem before it is a fitness problem."
    elif primary == "fueling":
        read = "That sounds fixable, but only if we find the first missed bottle or calories instead of blaming the final hour."
    elif primary == "pacing":
        read = "The useful clue is where the day changed, not how ugly the finish felt."
    elif primary == "mechanical":
        read = "That is a rotten way for fitness to become irrelevant."
    elif primary == "dns_deferred":
        read = "Deferring was probably the right call if getting to the line had already become the whole fight."
    elif primary == "logistics":
        read = "A logistics miss can spend a lot of legs before the race even starts."
    elif primary == "happy":
        read = "Sounds like the day did what you hoped it would."
    else:
        read = "I want to make sure I am reading the day correctly."

    body = [f"I read this part twice: {fragment}", read, DEBRIEF_QUESTIONS[primary]]

    weeks = facts.get("weeks_out") if facts else None
    has_next_race = bool(facts and weeks is not None and 0 <= weeks < 12)
    returning = primary != "injury" or bool(re.search(
        r"\b(return|returning|back (?:on|to)|cleared|riding again|training again)\b",
        result["text"].casefold(),
    ))
    offer_mode = primary in {"illness", "injury", "fueling", "pacing"}
    if offer_mode and has_next_race and returning:
        body.append(
            "If you want, I'll sketch the next 10 days for you — no charge, "
            "just tell me how week one feels."
        )

    return f"{hi}\n\n" + "\n\n".join(body) + "\n\n— Matti"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("race_query", nargs="?", help="race name or slug (fuzzy matched)")
    ap.add_argument("--debrief", action="store_true", help="draft a reply to a post-race response")
    ap.add_argument("--reply-file", help="debrief reply text file")
    ap.add_argument("--reply", help="debrief reply text, or - to read stdin")
    ap.add_argument("--race", dest="debrief_race", help="optional next race name or slug")
    ap.add_argument("--brand", choices=["gravel", "road"], default="gravel")
    ap.add_argument("--name", default="", help="rider first name")
    ap.add_argument("--copy", action="store_true", help="copy draft to clipboard (macOS)")
    args = ap.parse_args()

    brand = BRANDS[args.brand]
    if args.debrief:
        if bool(args.reply_file) == bool(args.reply):
            ap.error("--debrief requires exactly one of --reply-file or --reply")
        if args.reply_file:
            reply_text = Path(args.reply_file).read_text(encoding="utf-8")
        elif args.reply == "-":
            reply_text = sys.stdin.read()
        else:
            reply_text = args.reply or ""
        facts = None
        if args.debrief_race:
            path = find_race(args.debrief_race, brand["root"])
            if not path:
                print(f"No race matching {args.debrief_race!r} in {args.brand} database.")
                return 1
            facts = race_facts(path, brand["site"])
        text = draft_debrief(reply_text, args.name.strip().title(), facts)
        print(text)
        if args.copy:
            subprocess.run(["pbcopy"], input=text.encode())
            print("\n(copied to clipboard)")
        return 0

    if not args.race_query:
        ap.error("race is required unless --debrief is used")
    path = find_race(args.race_query, brand["root"])
    if not path:
        print(f"No race matching {args.race_query!r} in {args.brand} database.")
        return 1
    facts = race_facts(path, brand["site"])
    text = draft(facts, args.name.strip().title(), brand["plans_url"])

    weeks = ("?" if facts["weeks_out"] is None
             else f"{facts['weeks_out']:.1f} weeks out")
    header = (f"── {facts['name']} · {facts['date_text']} · "
              f"{weeks} · score {facts['score']}/100 ──")
    print(header)
    print(text)
    if args.copy:
        subprocess.run(["pbcopy"], input=text.encode())
        print("\n(copied to clipboard)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
