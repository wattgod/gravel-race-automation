#!/usr/bin/env python3
"""
A/B experiment configuration — source of truth for all running experiments.

Defines experiment variants, page targeting, traffic allocation, and
conversion events. Exports to web/ab/experiments.json for client-side
consumption without requiring page rebuilds.

Usage:
    python wordpress/ab_experiments.py          # export experiments.json
    python wordpress/ab_experiments.py --print  # print config to stdout
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "web" / "ab"

# ── Experiment definitions ───────────────────────────────────

EXPERIMENTS = [
    # NOTE: "homepage_hero_tagline" retired 2026-07-18 (ladder-strip-spec.md
    # ADDENDUM #1) \u2014 ran at 100% traffic with no end date on stale
    # hardcoded-count variants ("757 races") that would have clobbered the
    # new hero sub-line at runtime. data-ab="hero_tagline" was dropped from
    # generate_homepage.py's hero deck in the same change.
    {
        "id": "training_price_frame",
        "description": "Test price framing on training plans card",
        "selector": "[data-ab='training_price']",
        "pages": ["/", "/index.html", "/about/"],
        "traffic": 1.0,
        "start": "2026-02-16",
        "end": None,
        "variants": [
            {
                "id": "control",
                "name": "Hotel anchor",
                "content": "Race-specific. Built for your target event. Less than your race hotel \u2014 $2/day.",
            },
            {
                "id": "variant_a",
                "name": "Gel anchor",
                "content": "Race-specific. Built for your target event. $15/week. Less than one gel per ride.",
            },
            {
                "id": "variant_b",
                "name": "Entry fee anchor",
                "content": "Race-specific. Built for your target event. Your entry fee was $175. Your plan is $2/day.",
            },
        ],
        "conversion": {
            "type": "click",
            "selector": "[data-ab='training_cta_btn']",
        },
    },
    {
        "id": "cta_button_text",
        "description": "Test CTA button text on training plans",
        "selector": "[data-ab='training_cta_btn']",
        "pages": ["/", "/index.html", "/about/"],
        "traffic": 1.0,
        "start": "2026-02-16",
        "end": None,
        "variants": [
            {
                "id": "control",
                "name": "BUILD MY PLAN",
                "content": "BUILD MY PLAN",
            },
            {
                "id": "variant_a",
                "name": "GET MY PLAN",
                "content": "GET MY PLAN",
            },
            {
                "id": "variant_b",
                "name": "START TRAINING",
                "content": "START TRAINING",
            },
        ],
        "conversion": {
            "type": "click",
            "selector": "[data-ab='training_cta_btn']",
        },
    },
    {
        "id": "coaching_scarcity",
        "description": "Test scarcity framing on coaching card",
        "selector": "[data-ab='coaching_scarcity']",
        "pages": ["/", "/index.html", "/about/"],
        "traffic": 1.0,
        "start": "2026-02-16",
        "end": None,
        "variants": [
            {
                "id": "control",
                "name": "Generic scarcity",
                "content": "A human in your corner. Adapts week to week. Limited spots.",
            },
            {
                "id": "variant_a",
                "name": "Concrete number",
                "content": "A human in your corner. Adapts week to week. 20 athletes/month.",
            },
            {
                "id": "variant_b",
                "name": "Next window",
                "content": "A human in your corner. Adapts week to week. Next window: April.",
            },
        ],
        "conversion": {
            "type": "click",
            "selector": "[data-ga='coaching_click'], [data-cta='coaching_apply']",
        },
    },
    # ── Race page experiments (wildcard matching required) ──
    {
        "id": "race_sticky_cta_copy",
        "description": "Test sticky CTA text on race pages",
        "selector": "[data-ab='race_sticky_cta']",
        "pages": ["/race/*"],
        "traffic": 1.0,
        "start": "2026-03-25",
        "end": None,
        "variants": [
            {
                "id": "control",
                "name": "BUILD MY PLAN",
                "content": "BUILD MY PLAN \u2014 $15/WK",
            },
            {
                "id": "variant_a",
                "name": "Race-specific verb",
                "content": "TRAIN FOR THIS RACE \u2014 $15/WK",
            },
            {
                "id": "variant_b",
                "name": "Get plan",
                "content": "GET YOUR RACE PLAN \u2014 $15/WK",
            },
        ],
        "conversion": {
            "type": "click",
            "selector": "[data-cta='build_plan'], #gg-sticky-cta-link",
        },
    },
    {
        "id": "race_coaching_teaser",
        "description": "Test coaching teaser CTA copy on race pages",
        "selector": "[data-ab='race_coaching_cta']",
        "pages": ["/race/*"],
        "traffic": 1.0,
        "start": "2026-03-25",
        "end": None,
        "variants": [
            {
                "id": "control",
                "name": "Talk to a coach",
                "content": "TALK TO A COACH",
            },
            {
                "id": "variant_a",
                "name": "Apply for coaching",
                "content": "APPLY FOR COACHING",
            },
            {
                "id": "variant_b",
                "name": "Get a coach",
                "content": "GET A COACH FOR THIS RACE",
            },
        ],
        "conversion": {
            "type": "click",
            "selector": "[data-cta='coaching']",
        },
    },
]


def validate_experiments() -> list[str]:
    """Return list of validation errors (empty = valid)."""
    errors = []
    ids_seen = set()
    for exp in EXPERIMENTS:
        eid = exp.get("id", "<missing>")
        if not exp.get("id"):
            errors.append("Experiment missing 'id'")
            continue
        if eid in ids_seen:
            errors.append(f"Duplicate experiment id: {eid}")
        ids_seen.add(eid)

        if not exp.get("selector"):
            errors.append(f"{eid}: missing 'selector'")
        if not exp.get("variants") or len(exp["variants"]) < 2:
            errors.append(f"{eid}: need at least 2 variants")
        if not exp.get("pages"):
            errors.append(f"{eid}: missing 'pages'")

        variant_ids = set()
        has_control = False
        for v in exp.get("variants", []):
            vid = v.get("id", "<missing>")
            if not v.get("id"):
                errors.append(f"{eid}: variant missing 'id'")
            if vid in variant_ids:
                errors.append(f"{eid}: duplicate variant id: {vid}")
            variant_ids.add(vid)
            if vid == "control":
                has_control = True
            if not v.get("content"):
                errors.append(f"{eid}/{vid}: missing 'content'")
        if not has_control:
            errors.append(f"{eid}: no 'control' variant")

        traffic = exp.get("traffic", 1.0)
        if not (0 < traffic <= 1.0):
            errors.append(f"{eid}: traffic must be 0 < t <= 1.0, got {traffic}")

        if exp.get("start"):
            try:
                date.fromisoformat(exp["start"])
            except ValueError:
                errors.append(f"{eid}: invalid start date: {exp['start']}")
        if exp.get("end"):
            try:
                date.fromisoformat(exp["end"])
            except ValueError:
                errors.append(f"{eid}: invalid end date: {exp['end']}")

    return errors


def export_config() -> dict:
    """Return the client-side config dict (subset of full config)."""
    today = date.today().isoformat()
    active = []
    for exp in EXPERIMENTS:
        if exp.get("start") and exp["start"] > today:
            continue
        if exp.get("end") and exp["end"] < today:
            continue
        active.append({
            "id": exp["id"],
            "selector": exp["selector"],
            "pages": exp["pages"],
            "traffic": exp["traffic"],
            "variants": [
                {"id": v["id"], "name": v["name"], "content": v["content"]}
                for v in exp["variants"]
            ],
            "conversion": exp["conversion"],
        })
    return {"version": 1, "generated": today, "experiments": active}


def write_config():
    """Export experiments.json to web/ab/."""
    errors = validate_experiments()
    if errors:
        print("Validation errors:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = export_config()
    out_path = OUTPUT_DIR / "experiments.json"
    out_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    print(f"Exported {len(config['experiments'])} active experiment(s) to {out_path}")
    return config


def main():
    parser = argparse.ArgumentParser(description="A/B experiment config manager")
    parser.add_argument("--print", action="store_true", help="Print config to stdout")
    args = parser.parse_args()

    if args.print:
        errors = validate_experiments()
        if errors:
            for e in errors:
                print(f"  ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        config = export_config()
        print(json.dumps(config, indent=2, ensure_ascii=False))
    else:
        write_config()


if __name__ == "__main__":
    main()
