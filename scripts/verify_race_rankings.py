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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent))

import veracity_guards as vg

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
REVIEW_QUEUE_FILE = VERIFY_DIR / "review_queue.json"
INDEX_FILE = PROJECT_ROOT / "web" / "race-index.json"

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
                    "source_type": {
                        "type": "string",
                        "enum": ["official_site", "official_results",
                                 "media_outlet", "tracker", "other"],
                    },
                    "course_scope": {
                        "type": "string",
                        "enum": vg.COURSE_SCOPES,
                        "description": "Does web_value describe the race's standard flagship course, "
                                       "a one-off edition (reroute/detour/weather/fire), or a shorter option?",
                    },
                    "note": {"type": ["string", "null"]},
                },
                "required": ["field", "verdict", "web_value", "confidence",
                             "source_url", "source_type", "course_scope", "note"],
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


def _metric(vitals, key, unit):
    return f" ({vitals[key]} {unit})" if vitals.get(key) is not None else ""


def build_prompt(race):
    vitals = race.get("vitals", {})
    name = race.get("display_name") or race.get("name", "")
    return f"""Verify the current facts for the bike race "{name}" ({vitals.get('location', 'unknown location')}) using web search. Search for the race's official site and recent coverage. Today is {datetime.now(timezone.utc).date().isoformat()}.

Our database says:
- distance_mi: {vitals.get('distance_mi')}{_metric(vitals, 'distance_km', 'km')}
- elevation_ft: {vitals.get('elevation_ft')}{_metric(vitals, 'elevation_m', 'm')}
- field_size: {vitals.get('field_size')}
- prize_purse: {vitals.get('prize_purse')}
- registration_cost: {vitals.get('registration', '')}
- status: active (race is still being held)

For each field, report a verdict:
- "confirmed" if the web agrees (or is within normal reporting variance)
- "mismatch" if the web clearly disagrees — give the web value and source URL
- "unverifiable" if you cannot find reliable info

Source priority (strongest first): 1) the official race website, 2) official results, 3) reputable cycling media, 4) everything else; live trackers and GPS/activity sites (Dotwatcher, TrackLeaders, Strava, RideWithGPS...) are the weakest. Never report a mismatch from a weaker source when a stronger source agrees with our value. Report the source you actually used in source_url and its type in source_type.

Course scope: our profile describes the race's STANDARD FLAGSHIP course.
- A one-off change to a single edition (fire/weather/smoke detour, reroute, construction, a shortened year) is NOT a mismatch for the flagship value. If that is all you found, verdict "confirmed" or "unverifiable", course_scope "one_off_edition", and describe it in note.
- Never report a shorter course option (medio fondo, short route, half distance) as the race's distance. For multi-distance events, verify the longest/flagship distance that matches our value; if your value comes from a different option, set course_scope "shorter_option".
- course_scope "standard_course" only when the value is the race's normal flagship course.

Rules:
- Use high confidence only when the official site or 2+ independent sources agree.
- distance_mi and elevation_ft as plain numbers in miles/feet (convert km/m: 1 km = 0.621371 mi, 1 m = 3.28084 ft).
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




COURSE_FIELDS = ("distance_mi", "elevation_ft")


def _flag(changes, field, old, new, v, reason, **extra):
    """A change that is reported for a human but never written."""
    changes.append({"field": field, "old": old, "new": new,
                    "source": v.get("source_url"), "flag_only": True,
                    "reason": reason, "note": v.get("note"), **extra})


def _block_reason(race, vitals, field, v, old, new, tier, provenance):
    """Hard guards: a non-None reason means the value is never written."""
    if old and abs(new - old) / old > MAX_AUTO_REL_CHANGE:
        return "swing over 50%: likely a different distance variant", {}
    if field in COURSE_FIELDS:
        scope = vg.course_scope_block(v)
        if scope == "one_off":
            return ("one-off edition change (reroute/detour/weather): "
                    "recorded as a note, flagship value kept"), {"one_off": True}
        if scope == "shorter_option" or (
                field == "distance_mi" and vg.is_shorter_option(v, old, new)):
            return "shorter course option: flagship distance kept", {}
    if tier < vg.TIER_OUTLET:
        return f"weak source ({vg.TIER_NAMES[tier]})", {}
    backing = vg.existing_backing_tier(race, field, vitals.get(field), provenance)
    if tier < backing:
        return (f"{vg.TIER_NAMES[tier]} cannot overwrite a value backed by "
                f"{vg.TIER_NAMES[backing]}"), {}
    conflict = vg.unit_twin_conflict(vitals, field, new)
    if conflict:
        return f"unit check: {conflict}", {}
    return None, {}


def apply_fixes(slug, verdicts, dry_run, allow_review=False, provenance=None):
    """Apply whitelisted high-confidence fixes through the veracity guards.

    Each change dict has one disposition:
      flag_only     never written; reported for a human (one-offs become notes)
      needs_review  written only when allow_review=True (the review-PR pass)
      neither       safe to auto-commit to main
    A race is all-or-nothing: if any of its changes needs review, none of them
    are written in the auto pass, so a PR never carries half a correction.

    provenance: verify_state[slug]["sources"], which the bot records whenever a
    source confirms a value; see veracity_guards.existing_backing_tier.
    """
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
        tier = vg.source_tier(v.get("source_url"), race)

        if field in FIELD_TOLERANCE:
            old, new = _num(vitals.get(field)), _num(web_value)
            if old is None or new is None:
                continue
            if old and abs(new - old) / old <= FIELD_TOLERANCE[field]:
                continue  # within tolerance — treat as confirmed
            reason, extra = _block_reason(race, vitals, field, v, old, new,
                                          tier, provenance)
            if reason:
                _flag(changes, f"vitals.{field}", old, new, v, reason, **extra)
                continue
            review = []
            if field in COURSE_FIELDS:
                if vg.rel_change(old, new) > vg.MAX_AUTO_VITAL_REL_CHANGE:
                    review.append(f"{vg.rel_change(old, new):.0%} change (limit 15%)")
                if vg.looks_like_unit_mixup(field, old, new):
                    review.append("old to new is a unit conversion (km/mi or m/ft mix-up?)")
            if tier < vg.TIER_RESULTS:
                review.append(f"source is a {vg.TIER_NAMES[tier]}, not official")
            vitals[field] = str(int(new)) if field == "field_size" else int(new)
            changes.append({"field": f"vitals.{field}", "old": old, "new": new,
                            "source": v.get("source_url"),
                            "source_tier": vg.TIER_NAMES[tier],
                            "needs_review": bool(review),
                            "reason": "; ".join(review) or None})
        elif field == "prize_purse" and web_value:
            old = vitals.get("prize_purse")
            if str(old).strip().lower() == str(web_value).strip().lower():
                continue
            backing = vg.existing_backing_tier(race, field, old, provenance)
            if tier < vg.TIER_OUTLET or tier < backing:
                _flag(changes, "vitals.prize_purse", old, web_value, v,
                      f"{vg.TIER_NAMES[tier]} cannot overwrite a value backed by "
                      f"{vg.TIER_NAMES[backing]}" if tier >= vg.TIER_OUTLET
                      else f"weak source ({vg.TIER_NAMES[tier]})")
                continue
            vitals["prize_purse"] = web_value
            changes.append({"field": "vitals.prize_purse", "old": old,
                            "new": web_value, "source": v.get("source_url"),
                            "source_tier": vg.TIER_NAMES[tier],
                            "needs_review": tier < vg.TIER_RESULTS,
                            "reason": "source is not official" if tier < vg.TIER_RESULTS else None})
        elif field == "status" and web_value in ("cancelled", "paused", "defunct"):
            # Never auto-fix status — a false positive here kills a live page.
            _flag(changes, "status", "active", web_value, v, "status is flag-only")

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
            big = vg.score_delta_needs_review(old_score, new_score)
            changes.append({"field": f"rating.{score_field}",
                            "old": old_score, "new": new_score,
                            "source": "rubric recompute", "needs_review": big,
                            "reason": "criterion score moves 2+ points" if big else None})
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
            big = vg.score_delta_needs_review(old_overall, new_overall)
            changes.append({"field": "rating.overall_score",
                            "old": old_overall, "new": new_overall,
                            "source": "rubric recompute", "needs_review": big,
                            "reason": "overall score moves 2+ points" if big else None})
        if new_tier != old_tier:
            for k in ("tier", "editorial_tier", "display_tier"):
                rating[k] = new_tier
                rating[f"{k}_label"] = f"TIER {new_tier}"
            changes.append({"field": "rating.tier", "old": old_tier,
                            "new": new_tier, "source": "rubric recompute",
                            "tier_change": True})

    real_changes = [c for c in changes if not c.get("flag_only")]
    race_needs_review = any(c.get("needs_review") for c in real_changes)
    if race_needs_review:
        for c in real_changes:
            c["needs_review"] = True
    if real_changes and not dry_run and (allow_review or not race_needs_review):
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return changes


def written_changes(changes, allow_review=False):
    """The changes apply_fixes actually wrote (ignoring dry-run)."""
    real = [c for c in changes if not c.get("flag_only")]
    if not allow_review and any(c.get("needs_review") for c in real):
        return []
    return real


def _agrees(field, current, web_value):
    if field in FIELD_TOLERANCE:
        cur, web = _num(current), _num(web_value)
        if cur is None or web is None:
            return False
        return cur == web or (cur and abs(web - cur) / cur <= FIELD_TOLERANCE[field])
    return str(current).strip().lower() == str(web_value).strip().lower()


def record_provenance(entry, slug, verdicts, now):
    """Remember which source backs each current value, so a weaker source
    can't overwrite it next time. A stronger record is never downgraded."""
    race = json.loads((RACE_DATA / f"{slug}.json").read_text(encoding="utf-8"))["race"]
    vitals = race.get("vitals", {})
    sources = entry.setdefault("sources", {})
    for v in verdicts:
        field, url = v.get("field"), v.get("source_url")
        if field not in FIELD_TOLERANCE and field != "prize_purse":
            continue
        current = vitals.get(field)
        if not url or current is None:
            continue
        if v["verdict"] != "confirmed" and not _agrees(field, current, v.get("web_value")):
            continue
        tier = vg.source_tier(url, race)
        rec = sources.get(field)
        if rec and vg._same_value(rec.get("value"), current) and rec.get("tier", 0) > tier:
            continue
        sources[field] = {"value": current, "tier": tier, "url": url, "checked": now}


# --- Derived data: web/race-index.json + web/jsonld must move with profiles ---

def regenerate_derived():
    """The documented regeneration (data-pipeline-ops skill, section 1)."""
    subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "generate_index.py"),
                    "--with-jsonld"], cwd=PROJECT_ROOT, check=True,
                   stdout=subprocess.DEVNULL)


def index_drift(slugs):
    """Return one message per slug whose index entry disagrees with its profile."""
    if not INDEX_FILE.exists():
        return [f"{INDEX_FILE} missing"]
    index = {e.get("slug"): e for e in json.loads(INDEX_FILE.read_text(encoding="utf-8"))}
    drift = []
    for slug in slugs:
        race = json.loads((RACE_DATA / f"{slug}.json").read_text(encoding="utf-8"))["race"]
        rating, vitals = race.get("gravel_god_rating", {}), race.get("vitals", {})
        entry = index.get(slug)
        if entry is None:
            drift.append(f"{slug}: not in index")
            continue
        expected = {
            "overall_score": rating.get("overall_score"),
            "tier": rating.get("display_tier", rating.get("tier")),
            "distance_mi": vitals.get("distance_mi"),
            "elevation_ft": vitals.get("elevation_ft"),
        }
        for key, want in expected.items():
            got = entry.get(key)
            if want is None or got is None:
                continue
            if _num(want) != _num(got):
                drift.append(f"{slug}: {key} profile={want} index={got}")
    return drift


def publish_derived(slugs, regenerate=None):
    """Regenerate derived data for written profiles and prove it is in sync."""
    if not slugs:
        return []
    (regenerate or regenerate_derived)()
    return index_drift(slugs)


def render_review_pr_body(results):
    """Markdown for the human-review PR: old/new/source for every change."""
    lines = [
        "The rankings veracity bot found these corrections but they exceed its "
        "auto-commit limits (distance/elevation change over 15%, a score move of "
        "2+ points, or a non-official source), so a human has to check each source "
        "before merge. Close the PR to reject.",
        "",
        "Before merging: confirm each value describes the standard flagship course "
        "(not a one-off reroute or a shorter option), and update the matching "
        "`biased_opinion_ratings` explanation if a score moved.",
        "",
        "| Race | Field | Old | New | Source | Why review |",
        "|---|---|---|---|---|---|",
    ]
    flagged = []
    for slug, changes in results:
        for c in changes:
            if c.get("flag_only"):
                flagged.append(f"- `{slug}` {c['field']}: {c['old']} -> {c['new']} "
                               f"not written: {c.get('reason')} ({c.get('source')})")
                continue
            src = c.get("source") or ""
            if c.get("source_tier"):
                src = f"{src} ({c['source_tier']})"
            lines.append(f"| `{slug}` | {c['field']} | {c['old']} | {c['new']} | "
                         f"{src} | {c.get('reason') or ''} |")
    if flagged:
        lines += ["", "Flagged and NOT written (for context):", *flagged]
    lines += ["", "Index and JSON-LD regenerated with "
              "`python scripts/generate_index.py --with-jsonld`; "
              "`tests/test_index_integrity.py` passed before this PR was opened."]
    return "\n".join(lines) + "\n"


def apply_review_queue(queue_path, pr_body_path):
    """Second pass, run on a review branch: apply the queued races in full."""
    queue = json.loads(Path(queue_path).read_text(encoding="utf-8"))
    state = load_state()
    results, written = [], []
    for item in queue:
        slug = item["slug"]
        changes = apply_fixes(slug, item["verdicts"], dry_run=False, allow_review=True,
                              provenance=state.get(slug, {}).get("sources"))
        if written_changes(changes, allow_review=True):
            written.append(slug)
        results.append((slug, changes))
    drift = publish_derived(written)
    Path(pr_body_path).write_text(render_review_pr_body(results), encoding="utf-8")
    print(f"review queue: {len(written)} races applied for human review")
    if drift:
        print("INDEX DRIFT after regeneration:\n  " + "\n  ".join(drift))
        return 2
    return 0


def _tag(c):
    if c.get("flag_only"):
        return f" [FLAG-ONLY: {c.get('reason')}]"
    if c.get("needs_review"):
        return f" [REVIEW PR{': ' + c['reason'] if c.get('reason') else ''}]"
    return " [TIER CHANGE]" if c.get("tier_change") else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--slug")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--review-queue", default=str(REVIEW_QUEUE_FILE),
                    help="where races needing human review are queued")
    ap.add_argument("--apply-review-queue", metavar="QUEUE",
                    help="apply a queue written by a previous run (review branch only)")
    ap.add_argument("--pr-body", default=str(VERIFY_DIR / "review_pr_body.md"))
    args = ap.parse_args()

    if args.apply_review_queue:
        return apply_review_queue(args.apply_review_queue, args.pr_body)

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY from env
    state = load_state()
    slugs = select_races(state, args.limit, args.slug)
    now = datetime.now(timezone.utc).isoformat()

    report = {"run_at": now, "model": MODEL, "races": [], "errors": []}
    total_changes = 0
    written, review_queue = [], []

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

        entry = state.setdefault(slug, {})
        changes = apply_fixes(slug, result["fields"], args.dry_run,
                              provenance=entry.get("sources"))
        mismatches = [f for f in result["fields"] if f["verdict"] == "mismatch"]
        entry.update({"last_checked": now, "changed": bool(changes)})
        if written_changes(changes):
            written.append(slug)
            total_changes += len(written_changes(changes))
        if any(c.get("needs_review") for c in changes):
            review_queue.append({"slug": slug, "verdicts": result["fields"]})
        for c in changes:
            if c.get("one_off"):
                notes = entry.setdefault("one_off_notes", [])
                notes.append({"checked": now, "field": c["field"],
                              "value": c["new"], "source": c["source"],
                              "note": c.get("note")})
                del notes[:-5]
        if not args.dry_run:
            record_provenance(entry, slug, result["fields"], now)

        report["races"].append({
            "slug": slug,
            "verdicts": {f["field"]: f["verdict"] for f in result["fields"]},
            "mismatches": mismatches,
            "changes": changes,
            "usage": result.get("usage"),
        })

    exit_code = 0
    if not args.dry_run:
        VERIFY_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=1) + "\n")
        drift = publish_derived(written)
        report["index_drift"] = drift
        if drift:
            print("INDEX DRIFT after regeneration:\n  " + "\n  ".join(drift))
            exit_code = 2
        REPORT_FILE.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
        queue_path = Path(args.review_queue)
        if review_queue:
            queue_path.parent.mkdir(parents=True, exist_ok=True)
            queue_path.write_text(json.dumps(review_queue, indent=1, ensure_ascii=False) + "\n")
        elif queue_path.exists():
            queue_path.unlink()

    changed_races = [r for r in report["races"] if r["changes"]]
    flagged = [r for r in report["races"]
               if any(c.get("flag_only") or c.get("tier_change")
                      for c in r["changes"])]
    print(f"\n{len(slugs)} races checked, {len(changed_races)} with changes "
          f"({total_changes} fields auto-applied), {len(review_queue)} routed to "
          f"review PR, {len(flagged)} flagged for review, "
          f"{len(report['errors'])} errors")
    for r in changed_races:
        for c in r["changes"]:
            print(f"  {r['slug']}: {c['field']} {c['old']} -> {c['new']}{_tag(c)}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
