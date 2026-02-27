#!/usr/bin/env python3
"""Generate llms.txt and llms-full.txt per the llmstxt.org standard.

Produces two files:
  web/llms.txt      (~2KB) — brief description + links to machine-readable resources
  web/llms-full.txt (~200KB) — complete race database for LLM consumption

Usage:
    python scripts/generate_llms_txt.py           # Generate both files
    python scripts/generate_llms_txt.py --dry-run  # Preview sizes only
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_FILE = PROJECT_ROOT / "web" / "race-index.json"
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
OUTPUT_DIR = PROJECT_ROOT / "web"
SITE_URL = "https://gravelgodcycling.com"

TIER_LABELS = {1: "Tier 1 (Elite)", 2: "Tier 2 (Strong)", 3: "Tier 3 (Solid)", 4: "Tier 4 (Developing)"}

DIMENSIONS = [
    "logistics", "length", "technicality", "elevation", "climate",
    "altitude", "adventure", "prestige", "race_quality", "experience",
    "community", "field_depth", "value", "expenses",
]


def _num(val) -> float:
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0


def _fmt_elev(val) -> str:
    n = _num(val)
    if n == 0:
        return "—"
    return f"{int(n):,} ft"


def _fmt_dist(val) -> str:
    n = _num(val)
    if n == 0:
        return "—"
    if n == int(n):
        return f"{int(n)} mi"
    return f"{n:.1f} mi"


def _md_escape(val) -> str:
    """Escape a value for use inside a markdown table cell."""
    s = str(val) if val is not None else "—"
    return s.replace("|", "\\|").replace("\n", " ")


# ---------------------------------------------------------------------------
# llms.txt (brief)
# ---------------------------------------------------------------------------

def generate_llms_txt(index: list[dict]) -> str:
    """Generate the brief llms.txt file."""
    tier_counts = {}
    for r in index:
        t = r.get("tier", 4)
        tier_counts[t] = tier_counts.get(t, 0) + 1

    regions = sorted(set(r.get("region", "Unknown") for r in index if r.get("region")))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return f"""# Gravel God Race Database

> The definitive gravel race database. {len(index)} races rated on 14 criteria, scored 0-100, and tiered 1-4.
> Last generated: {now}

## Overview

Gravel God is an independent gravel cycling database covering {len(index)} races across North America and beyond. Every race is scored on 14 dimensions (logistics, length, technicality, elevation, climate, altitude, adventure, prestige, race quality, experience, community, field depth, value, expenses) on a 1-5 scale, producing an overall score out of 100 and a tier assignment (T1=elite, T2=strong, T3=solid, T4=developing).

- **Tier 1 (Elite)**: {tier_counts.get(1, 0)} races — score >= 80 or prestige override
- **Tier 2 (Strong)**: {tier_counts.get(2, 0)} races — score >= 60
- **Tier 3 (Solid)**: {tier_counts.get(3, 0)} races — score >= 45
- **Tier 4 (Developing)**: {tier_counts.get(4, 0)} races — score < 45

Disciplines: gravel, MTB, bikepacking.
Regions: {', '.join(regions)}.

## Machine-Readable Resources

- [Full LLM context (this database as text)]({SITE_URL}/llms-full.txt)
- [Race index JSON ({len(index)} entries)]({SITE_URL}/race-index.json)
- [REST API (OpenAPI)]({SITE_URL}/api/v1/docs)
- [RSS feed]({SITE_URL}/feed/races.xml)
- [MCP Server (GitHub)](https://github.com/wattgod/gravel-race-automation)
- [Individual race profiles]({SITE_URL}/race/{{slug}}/)
- [Markdown profiles]({SITE_URL}/race/{{slug}}/index.md)

## Contact

- Website: {SITE_URL}
- Email: matt@gravelgodcycling.com
"""


# ---------------------------------------------------------------------------
# llms-full.txt (comprehensive)
# ---------------------------------------------------------------------------

def _race_summary(slug: str, race_data_dir: Path) -> str:
    """Build a ~200-word summary for a T1/T2 race from its full profile."""
    f = race_data_dir / f"{slug}.json"
    if not f.exists():
        return ""

    try:
        data = json.loads(f.read_text())
    except (json.JSONDecodeError, KeyError):
        return ""

    rd = data.get("race", data)
    parts = []

    # One-liner verdict
    fv = rd.get("final_verdict", {})
    one_liner = fv.get("one_liner", "")
    if one_liner:
        parts.append(one_liner)

    # Course character
    course = rd.get("course_description", {})
    character = course.get("character", "")
    if character:
        parts.append(character)

    # Signature challenge
    sig = course.get("signature_challenge", "")
    if sig:
        parts.append(f"Signature challenge: {sig}")

    # Biased opinion summary (adds depth)
    bo = rd.get("biased_opinion", {})
    bo_summary = bo.get("summary", "")
    if bo_summary and bo_summary not in parts:
        parts.append(bo_summary)

    # Should you race it
    should = fv.get("should_you_race", "")
    if should:
        parts.append(should)

    # Non-negotiables
    nns = rd.get("non_negotiables", [])
    if nns:
        nn_text = "; ".join(
            nn.get("requirement", "") if isinstance(nn, dict) else str(nn)
            for nn in nns[:3]
        )
        if nn_text:
            parts.append(f"Non-negotiables: {nn_text}")

    return " ".join(parts)


def generate_llms_full_txt(index: list[dict], race_data_dir: Path) -> str:
    """Generate the comprehensive llms-full.txt file."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = []
    lines.append("# Gravel God Race Database — Full Context")
    lines.append("")
    lines.append(f"> {len(index)} gravel, MTB, and bikepacking races rated on 14 criteria.")
    lines.append(f"> Produced by Gravel God (gravelgodcycling.com). Generated: {now}")
    lines.append("")

    # Scoring methodology
    lines.append("## Scoring Methodology")
    lines.append("")
    lines.append("Each race is scored on 14 dimensions (1-5 scale):")
    lines.append(", ".join(DIMENSIONS) + ".")
    lines.append("")
    lines.append("Overall score = round((sum of 14 scores / 70) * 100).")
    lines.append("")
    lines.append("Tier assignment:")
    lines.append("- Tier 1 (Elite): score >= 80, OR prestige=5 + score>=75")
    lines.append("- Tier 2 (Strong): score >= 60, OR prestige=5 + score<75 (capped at T2)")
    lines.append("- Tier 3 (Solid): score >= 45")
    lines.append("- Tier 4 (Developing): score < 45")
    lines.append("- Prestige 4 promotes one tier (but not into T1)")
    lines.append("")

    # Sort: T1 first, then T2, T3, T4, each by score desc
    sorted_index = sorted(index, key=lambda r: (r.get("tier", 99), -(r.get("overall_score") or 0)))

    t1_t2 = [r for r in sorted_index if r.get("tier", 4) <= 2]
    t3_t4 = [r for r in sorted_index if r.get("tier", 4) >= 3]

    # T1/T2 races with summaries
    lines.append(f"## Tier 1 & Tier 2 Races ({len(t1_t2)} races)")
    lines.append("")

    for r in t1_t2:
        slug = r["slug"]
        name = _md_escape(r.get("name", slug))
        tier = r.get("tier", "?")
        score = r.get("overall_score", "?")
        dist = _fmt_dist(r.get("distance_mi"))
        elev = _fmt_elev(r.get("elevation_ft"))
        loc = _md_escape(r.get("location", "—"))
        month = _md_escape(r.get("month") or "—")
        disc = _md_escape(r.get("discipline") or "gravel")

        lines.append(f"### {name}")
        lines.append(f"Tier {tier} | Score: {score}/100 | {dist} | {elev} | {loc} | {month} | {disc}")
        lines.append(f"Profile: {SITE_URL}/race/{slug}/")

        summary = _race_summary(slug, race_data_dir)
        if summary:
            lines.append("")
            lines.append(summary)

        lines.append("")

    # T3/T4 races as table (now includes discipline)
    lines.append(f"## Tier 3 & Tier 4 Races ({len(t3_t4)} races)")
    lines.append("")
    lines.append("| Name | Tier | Score | Distance | Elevation | Location | Month | Discipline |")
    lines.append("|------|------|-------|----------|-----------|----------|-------|------------|")

    for r in t3_t4:
        name = _md_escape(r.get("name", r["slug"]))
        tier = r.get("tier", "?")
        score = r.get("overall_score", "?")
        dist = _fmt_dist(r.get("distance_mi"))
        elev = _fmt_elev(r.get("elevation_ft"))
        loc = _md_escape(r.get("location", "—"))
        month = _md_escape(r.get("month") or "—")
        disc = _md_escape(r.get("discipline") or "gravel")
        lines.append(f"| {name} | {tier} | {score} | {dist} | {elev} | {loc} | {month} | {disc} |")

    lines.append("")

    # Data schema
    lines.append("## Data Schema")
    lines.append("")
    lines.append("Each race profile (JSON) contains:")
    lines.append("- `race.name`, `race.slug`, `race.tagline`")
    lines.append("- `race.vitals`: distance_mi, elevation_ft, location, date, terrain_types, field_size")
    lines.append("- `race.gravel_god_rating`: overall_score, tier, 14 dimension scores, discipline")
    lines.append("- `race.course_description`: character, suffering_zones, signature_challenge")
    lines.append("- `race.terrain`: primary, surface, technical_rating, features")
    lines.append("- `race.climate`: primary, description, challenges")
    lines.append("- `race.logistics`: airport, lodging_strategy, official_site")
    lines.append("- `race.history`: founded, origin_story, notable_moments")
    lines.append("- `race.final_verdict`: one_liner, should_you_race, alternatives")
    lines.append("- `race.non_negotiables`: training requirements with deadlines")
    lines.append("- `race.citations`: source URLs")
    lines.append("- `race.tire_recommendations`: primary tires, pressure tables")
    lines.append("")
    lines.append(f"Access individual profiles at: {SITE_URL}/race/{{slug}}/")
    lines.append(f"Machine-readable JSON index: {SITE_URL}/race-index.json")
    lines.append(f"REST API: {SITE_URL}/api/v1/docs")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate llms.txt and llms-full.txt")
    parser.add_argument("--dry-run", action="store_true", help="Preview sizes only")
    args = parser.parse_args()

    if not INDEX_FILE.exists():
        print(f"ERROR: Race index not found: {INDEX_FILE}")
        return 1

    index = json.loads(INDEX_FILE.read_text())
    print(f"Loaded {len(index)} races from index")

    # Generate llms.txt
    llms_txt = generate_llms_txt(index)
    print(f"  llms.txt: {len(llms_txt):,} bytes")

    # Generate llms-full.txt
    llms_full = generate_llms_full_txt(index, RACE_DATA_DIR)
    print(f"  llms-full.txt: {len(llms_full):,} bytes")

    if args.dry_run:
        print("\n  [dry run] Would write to web/llms.txt and web/llms-full.txt")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "llms.txt").write_text(llms_txt)
    print(f"  Wrote: {OUTPUT_DIR / 'llms.txt'}")

    (OUTPUT_DIR / "llms-full.txt").write_text(llms_full)
    print(f"  Wrote: {OUTPUT_DIR / 'llms-full.txt'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
