#!/usr/bin/env python3
"""Rankings veracity checker — cheap agents verify the facts behind ratings.

For each selected race, one Haiku call with server-side web search verifies
the objective vitals that feed the Gravel God rating: distance, elevation
gain, field size, prize purse, registration cost, and whether the event is
still running. Dates are NOT checked here — the Tuesday fact-refresh loop
owns those (scrape_official_sites.py + fact_check_profiles.py).

Guardrails (mirrors weekly-fact-refresh):
  - Auto-fix only whitelisted FACT fields, only on high-confidence
    mismatches beyond tolerance. Subjective criteria (prestige, community,
    experience...) are never touched.
  - When distance/elevation change, the Length/Elevation criterion scores
    are recomputed from the published rubric (docs/GRAVEL_GOD_SCORING_SYSTEM.md),
    and overall_score/tier recomputed via recalculate_tiers logic.
  - Tier changes are applied but flagged loudly in the report.
  - The workflow's anomaly brake (>10 changed profiles) stops auto-commit.

Cost: ~$0.04/race (Haiku tokens + <=4 web searches at $10/1k). A 25-race
run is ~$1; weekly cadence sweeps all 757 races in ~30 weeks.

Usage:
  python scripts/verify_race_rankings.py --limit 25        # rotating batch
  python scripts/verify_race_rankings.py --slug unbound-200
  python scripts/verify_race_rankings.py --limit 5 --dry-run
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recalculate_tiers import (
    calculate_tier,
    apply_prestige_override,
    recalculate_score,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA = PROJECT_ROOT / "race-data"
VERIFY_DIR = PROJECT_ROOT / "data" / "verification"
STATE_FILE = VERIFY_DIR / "verify_state.json"
REPORT_FILE = VERIFY_DIR / "last_run_report.json"

MODEL = "claude-haiku-4-5"
MAX_SEARCHES_PER_RACE = 4

# Fields agents verify, with auto-fix tolerance (relative unless noted).
# A mismatch within tolerance counts as confirmed.
FIELD_TOLERANCE = {
    "distance_mi": 0.05,
    "elevation_ft": 0.15,
    "field_size": 0.25,   # sources report registered vs finishers; be loose
}
# A swing bigger than this is usually the agent verifying the wrong distance
# variant of a multi-distance event, not a real correction — flag, don't fix.
MAX_AUTO_REL_CHANGE = 0.5
# Verified but never auto-fixed numerically (string fields — replace whole value)
STRING_FIELDS = ["prize_purse", "registration_cost", "status"]

# Rubric thresholds (docs/GRAVEL_GOD_SCORING_SYSTEM.md) — score 1..5
LENGTH_THRESHOLDS = [(40, 1), (60, 2), (100, 3), (150, 4)]      # miles, else 5
ELEVATION_THRESHOLDS = [(2000, 1), (4000, 2), (6000, 3), (10000, 4)]  # ft, else 5

VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "enum": [
                            "distance_mi", "elevation_ft", "field_size",
                            "prize_purse", "registration_cost", "status",
                        ],
                    },
                    "verdict": {
                        "type": "string",
                        "enum": ["confirmed", "mismatch", "unverifiable"],
                    },
                    "web_value": {
                        "type": ["string", "null"],
                        "description": "Value found on the web, numeric fields as plain number string",
                    },
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "source_url": {"type": ["string", "null"]},
                    "note": {"type": ["string", "null"]},
                },
                "required": ["field", "verdict", "web_value", "confidence",
                             "source_url", "note"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["fields"],
    "additionalProperties": False,
}


def _num(val):
    """Coerce '1,200 ft' / '~500' / 4500 to float, else None."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    m = re.search(r"[\d,]+(?:\.\d+)?", str(val).replace(",", ""))
    return float(m.group(0)) if m else None


def score_from_thresholds(value, thresholds):
    for limit, score in thresholds:
        if value < limit:
            return score
    return 5


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def select_races(state, limit, slug=None):
    if slug:
        return [slug]
    slugs = sorted(p.stem for p in RACE_DATA.glob("*.json"))
    # Oldest-verified first; never-verified races come first.
    slugs.sort(key=lambda s: state.get(s, {}).get("last_checked", ""))
    return slugs[:limit]


def build_prompt(race):
    vitals = race.get("vitals", {})
    name = race.get("display_name") or race.get("name", "")
    return f"""Verify the current facts for the bike race "{name}" ({vitals.get('location', 'unknown location')}) using web search. Search for the race's official site and recent coverage. Today is {datetime.now(timezone.utc).date().isoformat()}.

Our database says:
- distance_mi: {vitals.get('distance_mi')}
- elevation_ft: {vitals.get('elevation_ft')}
- field_size: {vitals.get('field_size')}
- prize_purse: {vitals.get('prize_purse')}
- registration_cost: {vitals.get('registration', '')}
- status: active (race is still being held)

For each field, report a verdict:
- "confirmed" if the web agrees (or is within normal reporting variance)
- "mismatch" if the web clearly disagrees — give the web value and source URL
- "unverifiable" if you cannot find reliable info

Rules:
- Prefer the official race website; use high confidence only when the official site or 2+ independent sources agree.
- For multi-distance events, verify THE distance listed above (races have separate profiles per distance).
- distance_mi and elevation_ft as plain numbers in miles/feet (convert km/m).
- status: "cancelled", "paused", or "defunct" ONLY with clear evidence (official announcement, no edition for 2+ years); otherwise "active".
- Do not guess. "unverifiable" is a valid, safe answer."""


def verify_race(client, slug):
    data = json.loads((RACE_DATA / f"{slug}.json").read_text(encoding="utf-8"))
    race = data["race"]

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": MAX_SEARCHES_PER_RACE,
        }],
        output_config={"format": {"type": "json_schema", "schema": VERIFY_SCHEMA}},
        messages=[{"role": "user", "content": build_prompt(race)}],
    )

    if response.stop_reason == "refusal":
        return {"slug": slug, "error": "refusal", "fields": []}

    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        return {"slug": slug, "error": "unparseable", "fields": []}

    result["slug"] = slug
    usage = response.usage
    result["usage"] = {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
    }
    return result


def apply_fixes(slug, verdicts, dry_run):
    """Apply whitelisted high-confidence fixes. Returns list of change dicts."""
    path = RACE_DATA / f"{slug}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    race = data["race"]
    vitals = race.setdefault("vitals", {})
    rating = race.get("gravel_god_rating", {})
    changes = []

    for v in verdicts:
        if v["verdict"] != "mismatch" or v["confidence"] != "high":
            continue
        field, web_value = v["field"], v["web_value"]

        if field in FIELD_TOLERANCE:
            old, new = _num(vitals.get(field)), _num(web_value)
            if old is None or new is None:
                continue
            if old and abs(new - old) / old <= FIELD_TOLERANCE[field]:
                continue  # within tolerance — treat as confirmed
            if old and abs(new - old) / old > MAX_AUTO_REL_CHANGE:
                changes.append({"field": f"vitals.{field}", "old": old,
                                "new": new, "source": v["source_url"],
                                "flag_only": True})
                continue
            if field == "field_size":
                vitals[field] = str(int(new))
            else:
                vitals[field] = int(new)
            changes.append({"field": f"vitals.{field}", "old": old, "new": new,
                            "source": v["source_url"]})
        elif field == "prize_purse" and web_value:
            old = vitals.get("prize_purse")
            if str(old).strip().lower() != str(web_value).strip().lower():
                vitals["prize_purse"] = web_value
                changes.append({"field": "vitals.prize_purse", "old": old,
                                "new": web_value, "source": v["source_url"]})
        elif field == "status" and web_value in ("cancelled", "paused", "defunct"):
            # Never auto-fix status — a false positive here kills a live page.
            changes.append({"field": "status", "old": "active", "new": web_value,
                            "source": v["source_url"], "flag_only": True})

    # Recompute rubric-derived scores if their inputs changed
    score_changed = False
    for vital_field, score_field, thresholds in (
        ("distance_mi", "length", LENGTH_THRESHOLDS),
        ("elevation_ft", "elevation", ELEVATION_THRESHOLDS),
    ):
        if not any(c["field"] == f"vitals.{vital_field}" and not c.get("flag_only")
                   for c in changes):
            continue
        new_score = score_from_thresholds(_num(vitals[vital_field]), thresholds)
        old_score = rating.get(score_field)
        if old_score is not None and new_score != old_score:
            rating[score_field] = new_score
            score_changed = True
            changes.append({"field": f"rating.{score_field}",
                            "old": old_score, "new": new_score,
                            "source": "rubric recompute"})
            # biased_opinion_ratings mirrors the same criteria as
            # {score, explanation} objects; tests enforce score parity
            # between the two blocks, so sync the twin or the fix fails CI.
            bor = race.get("biased_opinion_ratings", {}).get(score_field)
            if isinstance(bor, dict) and bor.get("score") != new_score:
                changes.append({"field": f"biased_opinion_ratings.{score_field}.score",
                                "old": bor.get("score"), "new": new_score,
                                "source": "rubric recompute (sync)"})
                bor["score"] = new_score

    if score_changed:
        old_overall, old_tier = rating.get("overall_score"), rating.get("display_tier")
        new_overall = recalculate_score(rating)
        base_tier = calculate_tier(new_overall)
        new_tier, _ = apply_prestige_override(
            base_tier, rating.get("prestige", 0), new_overall)
        if new_overall != old_overall:
            rating["overall_score"] = new_overall
            changes.append({"field": "rating.overall_score",
                            "old": old_overall, "new": new_overall,
                            "source": "rubric recompute"})
        if new_tier != old_tier:
            for k in ("tier", "editorial_tier", "display_tier"):
                rating[k] = new_tier
                rating[f"{k}_label"] = f"TIER {new_tier}"
            changes.append({"field": "rating.tier", "old": old_tier,
                            "new": new_tier, "source": "rubric recompute",
                            "tier_change": True})

    real_changes = [c for c in changes if not c.get("flag_only")]
    if real_changes and not dry_run:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--slug")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY from env
    state = load_state()
    slugs = select_races(state, args.limit, args.slug)
    now = datetime.now(timezone.utc).isoformat()

    report = {"run_at": now, "model": MODEL, "races": [], "errors": []}
    total_changes = 0

    for slug in slugs:
        print(f"verifying {slug}...", flush=True)
        try:
            result = verify_race(client, slug)
        except anthropic.APIError as e:
            report["errors"].append({"slug": slug, "error": str(e)[:200]})
            continue

        if result.get("error"):
            report["errors"].append({"slug": slug, "error": result["error"]})
            continue

        changes = apply_fixes(slug, result["fields"], args.dry_run)
        mismatches = [f for f in result["fields"] if f["verdict"] == "mismatch"]
        state[slug] = {"last_checked": now, "changed": bool(changes)}
        total_changes += len([c for c in changes if not c.get("flag_only")])

        report["races"].append({
            "slug": slug,
            "verdicts": {f["field"]: f["verdict"] for f in result["fields"]},
            "mismatches": mismatches,
            "changes": changes,
            "usage": result.get("usage"),
        })

    if not args.dry_run:
        VERIFY_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=1) + "\n")
        REPORT_FILE.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")

    changed_races = [r for r in report["races"] if r["changes"]]
    flagged = [r for r in report["races"]
               if any(c.get("flag_only") or c.get("tier_change")
                      for c in r["changes"])]
    print(f"\n{len(slugs)} races checked, {len(changed_races)} with changes "
          f"({total_changes} fields), {len(flagged)} flagged for review, "
          f"{len(report['errors'])} errors")
    for r in changed_races:
        for c in r["changes"]:
            tag = " [FLAG-ONLY]" if c.get("flag_only") else (
                  " [TIER CHANGE]" if c.get("tier_change") else "")
            print(f"  {r['slug']}: {c['field']} {c['old']} -> {c['new']}{tag}")


if __name__ == "__main__":
    main()
