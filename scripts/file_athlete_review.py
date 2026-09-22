#!/usr/bin/env python3
"""File a coached athlete's season review into their Endure record.

Reads the answers Mission Control stored when the athlete submitted
/coaching/season-review/athlete/, and writes them where Endure already keeps
this material (endurelabs docs/specs/endure-loop-2026.md §3):

  extended_profile.interrogation[]     the probes, verbatim
  extended_profile.limiter_evidence[]  the rate limiter, typed, with evidence
  extended_profile.limiters[]          a string projection, so every existing
                                       reader keeps working
  extended_profile.drop_order[]        what goes first when a week collapses
  extended_profile.season_review       the whole answer set, dated

It never creates goals: a goal without a habit can't go active anyway, and
Matti builds those himself. Prints exactly what it would write and changes
nothing unless you pass --apply.

Credentials, read from the environment or the repo .env files:
  SUPABASE_URL / SUPABASE_SERVICE_KEY            Mission Control (read)
  ENDURE_SUPABASE_URL / ENDURE_SERVICE_ROLE_KEY  Endure (write); falls back to
    NEXT_PUBLIC_SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY from
    endurelabs/.env.local

Usage:
  python3 scripts/file_athlete_review.py --list
  python3 scripts/file_athlete_review.py --email rider@example.com
  python3 scripts/file_athlete_review.py --email rider@example.com --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENDURE_ENV = Path.home() / "Documents" / "GravelGod" / "endurelabs" / ".env.local"

PROBE_FIELDS = [
    ("limiter", "Rate limiter: the one thing to fix"),
    ("limiter_evidence", "Rate limiter: the evidence"),
    ("vices", "Admitted vices: what is costing you, how often, when"),
    ("skill_gaps", "Skill shortcomings: where races are lost that fitness does not explain"),
    ("week_breakers", "Life constraints: what breaks a training week, and how often"),
    ("drop_order", "Drop order: when the week collapses, what goes first"),
    ("pre_race_48h", "The 48 hours before the last race"),
    ("admission", "The admission: what they would have to admit"),
]


def _load_env_file(path: Path) -> dict:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _creds() -> tuple[dict, dict]:
    mc_env = {
        **_load_env_file(Path.home() / "Documents" / "GravelGod" / "gravel-race-automation" / ".env"),
        **_load_env_file(REPO_ROOT / ".env"),
        **os.environ,
    }
    mc = {
        "url": mc_env.get("SUPABASE_URL", ""),
        "key": mc_env.get("SUPABASE_SERVICE_KEY", ""),
    }
    endure_env = {**_load_env_file(ENDURE_ENV), **os.environ}
    endure = {
        "url": endure_env.get("ENDURE_SUPABASE_URL") or endure_env.get("NEXT_PUBLIC_SUPABASE_URL", ""),
        "key": endure_env.get("ENDURE_SERVICE_ROLE_KEY") or endure_env.get("SUPABASE_SERVICE_ROLE_KEY", ""),
    }
    return mc, endure


def _rest(creds: dict, path: str, method: str = "GET", body=None) -> list | dict:
    url = creds["url"].rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {
        "apikey": creds["key"],
        "Authorization": f"Bearer {creds['key']}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode()
            return json.loads(text) if text else []
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path} failed: {e.code} {e.read().decode()[:300]}")


def fetch_reviews(mc: dict, email: str | None) -> list[dict]:
    query = ("/rest/v1/gg_sequence_enrollments?source=eq.athlete_review"
             "&select=contact_email,contact_name,source_data,enrolled_at"
             "&order=enrolled_at.desc&limit=50")
    if email:
        # filter server-side: a name match past the 50th row would otherwise
        # look like "no review found"
        query += "&contact_email=eq." + urllib.parse.quote(email)
    return _rest(mc, query)


def build_updates(answers: dict, submitted_at: str) -> dict:
    """The shapes Endure already reads, built from the answers."""
    interrogation = [
        {"probe": label, "field": field, "answer": answers[field],
         "asked_at": submitted_at, "version": 1}
        for field, label in PROBE_FIELDS if answers.get(field)
    ]
    updates: dict = {"season_review": {"filed_at": submitted_at, "answers": answers}}
    if interrogation:
        updates["interrogation"] = interrogation
    if answers.get("limiter"):
        updates["limiter_evidence"] = [{
            "v": 1,
            "text": answers["limiter"],
            "kind": answers.get("limiter_kind"),
            "evidence": answers.get("limiter_evidence"),
            "admitted_at": submitted_at,
        }]
        updates["limiters"] = [answers["limiter"]]
    if answers.get("drop_order"):
        import re as _re
        parts = [p.strip() for p in _re.split(r",|→|->|\bthen\b", answers["drop_order"])]
        updates["drop_order"] = [p for p in parts if p]
    return updates


def merge_profile(existing: dict, updates: dict) -> tuple[dict, list[str]]:
    """Add to what Endure already holds; never replace it.

    `limiters` is read by the coach profile tab, the habit proposals and the
    goals settings, and is written by onboarding — replacing it would delete
    an athlete's history. The spec's interrogation, limiter_evidence and
    drop_order are appended lists, so new entries go on the end.
    """
    profile = dict(existing)
    notes: list[str] = []
    for key, value in updates.items():
        if key in ("interrogation", "limiter_evidence") and isinstance(value, list):
            before = list(profile.get(key) or [])
            profile[key] = before + value
            notes.append(f"{key}: {len(before)} existing kept, {len(value)} appended")
        elif key == "limiters" and isinstance(value, list):
            before = [x for x in (profile.get(key) or []) if isinstance(x, str)]
            added = [v for v in value if v not in before]
            profile[key] = before + added
            notes.append(f"limiters: {len(before)} existing kept, {len(added)} added")
        else:
            if key in profile:
                notes.append(f"{key}: replaces the previous value")
            profile[key] = value
    return profile, notes


def find_athlete(endure: dict, email: str) -> dict | None:
    rows = _rest(
        endure,
        "/rest/v1/athletes?select=id,name,email,extended_profile&email=eq."
        + urllib.parse.quote(email) + "&limit=1",
    )
    return rows[0] if rows else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", help="athlete's email as they entered it")
    parser.add_argument("--list", action="store_true", help="list filed reviews and exit")
    parser.add_argument("--apply", action="store_true", help="actually write to Endure")
    args = parser.parse_args()

    mc, endure = _creds()
    if not mc["url"] or not mc["key"]:
        return _fail("Mission Control credentials missing (SUPABASE_URL / SUPABASE_SERVICE_KEY)")

    reviews = fetch_reviews(mc, args.email)
    if args.list or not args.email:
        if not reviews:
            print("No season reviews filed yet.")
            return 0
        print(f"{len(reviews)} review(s):\n")
        for r in reviews:
            sd = r.get("source_data") or {}
            print(f"  {r['enrolled_at'][:16]}  {r.get('contact_name') or '(no name)':<24} "
                  f"{r['contact_email']:<32} athlete={sd.get('athlete') or '-'} "
                  f"answers={len(sd.get('goal_answers') or {})}")
        print("\nFile one:  --email <address>   (add --apply to write)")
        return 0

    if not reviews:
        return _fail(f"No review found for {args.email}")

    row = reviews[0]
    answers = (row.get("source_data") or {}).get("goal_answers") or {}
    if not answers:
        return _fail("That review carries no answers")
    updates = build_updates(answers, row.get("enrolled_at") or datetime.now(timezone.utc).isoformat())

    print(f"\nReview from {row.get('contact_name') or row['contact_email']} "
          f"({row['enrolled_at'][:16]}), {len(answers)} answers\n")
    for key, value in updates.items():
        rendered = json.dumps(value, indent=1)
        print(f"  extended_profile.{key}:")
        print("    " + rendered.replace("\n", "\n    ")[:600] + ("…" if len(rendered) > 600 else ""))
        print()

    if not endure["url"] or not endure["key"]:
        return _fail("Endure credentials missing (ENDURE_SUPABASE_URL / ENDURE_SERVICE_ROLE_KEY, "
                     f"or endurelabs/.env.local at {ENDURE_ENV})")

    athlete = find_athlete(endure, row["contact_email"])
    if not athlete:
        return _fail(f"No Endure athlete has the email {row['contact_email']}. "
                     "Check the address they used, or file it by hand.")
    print(f"Endure athlete: {athlete.get('name') or '(unnamed)'}  id={athlete['id']}")

    existing = athlete.get("extended_profile") or {}
    profile, notes = merge_profile(existing, updates)
    for note in notes:
        print(f"  · {note}")

    if not args.apply:
        print("\nDry run. Nothing written. Add --apply to write this into their record.")
        return 0

    backup = Path(f"athlete-profile-backup-{athlete['id']}-{int(datetime.now(timezone.utc).timestamp())}.json")
    backup.write_text(json.dumps(existing, indent=1))
    print(f"\nBacked up their current profile to {backup}")

    _rest(endure, f"/rest/v1/athletes?id=eq.{athlete['id']}", method="PATCH",
          body={"extended_profile": profile})
    print("✓ Written to Endure. David and the coach view read extended_profile.")
    return 0


def _fail(message: str) -> int:
    print(f"✗ {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
