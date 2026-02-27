#!/usr/bin/env python3
"""Generate machine-readable Markdown profiles for all races.

Produces web/markdown/{slug}.md for each race with YAML frontmatter
and structured sections. Designed for AI agents, scrapers, and the
llmstxt.org ecosystem.

Usage:
    python scripts/generate_markdown_profiles.py           # Generate all
    python scripts/generate_markdown_profiles.py --dry-run  # Preview only
    python scripts/generate_markdown_profiles.py --slug unbound-200  # Single race
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
OUTPUT_DIR = PROJECT_ROOT / "web" / "markdown"
SITE_URL = "https://gravelgodcycling.com"

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


def _safe(val, default=""):
    """Return val if not None, else default. Preserves 0 and empty string."""
    if val is None:
        return default
    return val


def _md_escape(val) -> str:
    """Escape a value for use inside a markdown table cell."""
    if val is None:
        return ""
    s = str(val)
    return s.replace("|", "\\|").replace("\n", " ")


def _fmt_elev(val) -> str:
    n = _num(val)
    if n == 0:
        return ""
    return f"{int(n):,} ft"


def _fmt_dist(val) -> str:
    n = _num(val)
    if n == 0:
        return ""
    if n == int(n):
        return f"{int(n)} mi"
    return f"{n:.1f} mi"


# ---------------------------------------------------------------------------
# YAML frontmatter
# ---------------------------------------------------------------------------

def _yaml_escape(val) -> str:
    """Escape a value for YAML. Always wraps strings in double quotes for safety.
    
    Handles internal double quotes by escaping them with backslash.
    Numeric and boolean types are returned as-is.
    """
    if isinstance(val, (int, float)):
        return str(val)
    s = str(val)
    # Escape backslashes first, then double quotes
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def _frontmatter(slug: str, index_entry: dict, rd: dict) -> str:
    """Build YAML frontmatter block."""
    vitals = rd.get("vitals", {})
    rating = rd.get("gravel_god_rating", {})

    fields = {
        "slug": slug,
        "name": rd.get("name", slug),
        "tier": rating.get("tier") or rating.get("display_tier") or index_entry.get("tier", 4),
        "score": rating.get("overall_score") or index_entry.get("overall_score", 0),
        "distance_mi": _safe(vitals.get("distance_mi"), _safe(index_entry.get("distance_mi"), 0)),
        "elevation_ft": _safe(vitals.get("elevation_ft"), _safe(index_entry.get("elevation_ft"), 0)),
        "location": _safe(vitals.get("location"), _safe(index_entry.get("location"), "")),
        "region": _safe(index_entry.get("region"), ""),
        "month": _safe(index_entry.get("month"), ""),
        "discipline": _safe(rating.get("discipline"), _safe(index_entry.get("discipline"), "gravel")),
        "date": _safe(vitals.get("date_specific"), _safe(vitals.get("date"), "")),
        "url": f"{SITE_URL}/race/{slug}/",
    }

    lines = ["---"]
    for k, v in fields.items():
        if v is None or v == "":
            continue
        lines.append(f"{k}: {_yaml_escape(v)}")
    lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _section_vitals(rd: dict) -> str:
    """Build Vitals table."""
    vitals = rd.get("vitals", {})
    if not vitals:
        return ""

    rows = []
    if vitals.get("distance_mi") is not None:
        rows.append(f"| Distance | {_md_escape(_fmt_dist(vitals['distance_mi']))} |")
    if vitals.get("elevation_ft") is not None:
        rows.append(f"| Elevation | {_md_escape(_fmt_elev(vitals['elevation_ft']))} |")
    if vitals.get("location"):
        rows.append(f"| Location | {_md_escape(vitals['location'])} |")
    date_val = _safe(vitals.get("date_specific"), _safe(vitals.get("date"), ""))
    if date_val:
        rows.append(f"| Date | {_md_escape(date_val)} |")
    if vitals.get("terrain_types"):
        rows.append(f"| Terrain | {_md_escape(', '.join(vitals['terrain_types']))} |")
    if vitals.get("field_size"):
        rows.append(f"| Field Size | {_md_escape(vitals['field_size'])} |")
    if vitals.get("registration"):
        rows.append(f"| Registration | {_md_escape(vitals['registration'])} |")

    if not rows:
        return ""

    header = "## Vitals\n\n| | |\n|---|---|\n"
    return header + "\n".join(rows)


def _section_course(rd: dict) -> str:
    """Build Course section."""
    course = rd.get("course_description", {})
    if not course:
        return ""

    parts = ["## Course"]

    if course.get("character"):
        parts.append(f"\n{course['character']}")

    if course.get("suffering_zones"):
        parts.append("\n### Suffering Zones\n")
        for sz in course["suffering_zones"]:
            label = _safe(sz.get("label"), sz.get("named_section", ""))
            mile = sz.get("mile", "")
            desc = _safe(sz.get("desc"), "")
            if label:
                parts.append(f"- **Mile {mile} — {label}**: {desc}")

    if course.get("signature_challenge"):
        parts.append(f"\n### Signature Challenge\n\n{course['signature_challenge']}")

    return "\n".join(parts)


def _section_terrain(rd: dict) -> str:
    """Build Terrain section."""
    terrain = rd.get("terrain", {})
    if not terrain:
        return ""
    if isinstance(terrain, str):
        return f"## Terrain\n\n{terrain}"

    parts = ["## Terrain"]
    if terrain.get("primary"):
        parts.append(f"\n{terrain['primary']}")
    if terrain.get("surface"):
        parts.append(f"\nSurface: {terrain['surface']}")
    if terrain.get("features"):
        parts.append("\nFeatures:")
        for f in terrain["features"]:
            parts.append(f"- {f}")

    return "\n".join(parts)


def _section_climate(rd: dict) -> str:
    """Build Climate section."""
    climate = rd.get("climate", {})
    if not climate:
        return ""

    parts = ["## Climate"]
    if climate.get("primary"):
        parts.append(f"\n{climate['primary']}")
    if climate.get("description"):
        parts.append(f"\n{climate['description']}")
    if climate.get("challenges"):
        parts.append("\nChallenges:")
        for c in climate["challenges"]:
            parts.append(f"- {c}")

    return "\n".join(parts)


def _section_rating(rd: dict) -> str:
    """Build Gravel God Rating section with 14-dimension table."""
    rating = rd.get("gravel_god_rating", {})
    if not rating:
        return ""

    parts = [
        "## Gravel God Rating",
        f"\n**Overall Score**: {rating.get('overall_score', '?')}/100",
        f"**Tier**: {rating.get('tier', '?')}",
        f"**Discipline**: {_safe(rating.get('discipline'), 'gravel')}",
        "\n| Dimension | Score |",
        "|-----------|-------|",
    ]

    for dim in DIMENSIONS:
        val = rating.get(dim, "—")
        parts.append(f"| {dim.replace('_', ' ').title()} | {val}/5 |")

    return "\n".join(parts)


def _section_verdict(rd: dict) -> str:
    """Build The Verdict section."""
    fv = rd.get("final_verdict", {})
    if not fv:
        return ""

    parts = ["## The Verdict"]
    if fv.get("one_liner"):
        parts.append(f"\n> {fv['one_liner']}")
    if fv.get("should_you_race"):
        parts.append(f"\n### Should You Race It?\n\n{fv['should_you_race']}")
    if fv.get("alternatives"):
        parts.append(f"\n### Alternatives\n\n{fv['alternatives']}")

    return "\n".join(parts)


def _section_logistics(rd: dict) -> str:
    """Build Logistics section."""
    logistics = rd.get("logistics", {})
    if not logistics:
        return ""

    parts = ["## Logistics"]
    for key in ("airport", "lodging_strategy", "food", "packet_pickup", "parking", "camping", "official_site"):
        val = logistics.get(key)
        if val:
            label = key.replace("_", " ").title()
            if key == "official_site":
                parts.append(f"\n**Official Site**: {val}")
            else:
                parts.append(f"\n**{label}**: {val}")

    return "\n".join(parts)


def _section_history(rd: dict) -> str:
    """Build History section."""
    history = rd.get("history", {})
    if not history:
        return ""

    parts = ["## History"]
    if history.get("founded"):
        parts.append(f"\nFounded: {history['founded']}")
    if history.get("founder"):
        parts.append(f"Founder: {history['founder']}")
    if history.get("origin_story"):
        parts.append(f"\n{history['origin_story']}")
    if history.get("reputation"):
        parts.append(f"\n{history['reputation']}")

    return "\n".join(parts)


def _section_non_negotiables(rd: dict) -> str:
    """Build Non-Negotiables section."""
    nns = rd.get("non_negotiables", [])
    if not nns:
        return ""

    parts = ["## Non-Negotiables\n"]
    for nn in nns:
        if isinstance(nn, dict):
            req = nn.get("requirement", "")
            by_when = nn.get("by_when", "")
            why = nn.get("why", "")
            parts.append(f"- **{req}** (by {by_when}): {why}")
        else:
            parts.append(f"- {nn}")

    return "\n".join(parts)


def _section_riders_report(rd: dict) -> str:
    """Build Riders Report section from rider_intel."""
    yt = rd.get("youtube_data", {})
    intel = yt.get("rider_intel", {})
    if not intel:
        return ""

    parts = ["## Riders Report\n"]
    parts.append("*From YouTube race footage transcripts.*\n")

    if intel.get("key_challenges"):
        parts.append("### Key Challenges\n")
        for c in intel["key_challenges"]:
            parts.append(f"- {c}")

    if intel.get("terrain_notes"):
        parts.append("\n### Terrain Notes\n")
        for t in intel["terrain_notes"]:
            parts.append(f"- {t}")

    if intel.get("gear_mentions"):
        parts.append("\n### Gear Mentions\n")
        for g in intel["gear_mentions"]:
            parts.append(f"- {g}")

    if intel.get("race_day_tips"):
        parts.append("\n### Race Day Tips\n")
        for tip in intel["race_day_tips"]:
            parts.append(f"- {tip}")

    if intel.get("additional_quotes"):
        parts.append("\n### Rider Quotes\n")
        for q in intel["additional_quotes"]:
            if isinstance(q, dict):
                parts.append(f'> "{q.get("text", "")}" — {q.get("source", "")}')
            else:
                parts.append(f"> {q}")

    return "\n".join(parts)


def _section_tires(rd: dict) -> str:
    """Build Tire Recommendations section."""
    tires = rd.get("tire_recommendations", {})
    if not tires:
        return ""

    primary = tires.get("primary", [])
    if not primary:
        return ""

    parts = ["## Tire Recommendations\n"]
    width = tires.get("recommended_width_mm")
    if width is not None:
        parts.append(f"Recommended width: {width}mm\n")

    for t in primary:
        name = t.get("name", "Unknown")
        w = t.get("recommended_width_mm", "")
        why = t.get("why", "")
        parts.append(f"- **{name}** ({w}mm): {why}")

    split = tires.get("front_rear_split", {})
    if split.get("applicable") and split.get("front") and split.get("rear"):
        front = split["front"]
        rear = split["rear"]
        parts.append(f"\n**Front/Rear Split**: {front.get('name', '')} {front.get('width_mm', '')}mm / {rear.get('name', '')} {rear.get('width_mm', '')}mm")
        if split.get("rationale"):
            parts.append(f"Rationale: {split['rationale']}")

    return "\n".join(parts)


def _section_citations(rd: dict) -> str:
    """Build Citations section."""
    cites = rd.get("citations", [])
    if not cites:
        return ""

    # Deduplicate by URL
    seen_urls = set()
    unique_cites = []
    for c in cites:
        url = c.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_cites.append(c)

    if not unique_cites:
        return ""

    parts = ["## Citations\n"]
    for c in unique_cites:
        label = c.get("label", c.get("url", ""))
        url = c.get("url", "")
        cat = c.get("category", "")
        parts.append(f"- [{label}]({url}) ({cat})")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Profile builder
# ---------------------------------------------------------------------------

def generate_profile(slug: str, index_entry: dict, race_data_dir: Path) -> str | None:
    """Generate a complete Markdown profile for a single race."""
    f = race_data_dir / f"{slug}.json"
    if not f.exists():
        return None

    try:
        data = json.loads(f.read_text())
    except (json.JSONDecodeError, KeyError):
        return None

    rd = data.get("race", data)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    sections = [
        _frontmatter(slug, index_entry, rd),
        f"\n# {rd.get('name', slug)}",
    ]

    tagline = rd.get("tagline", "")
    if tagline:
        sections.append(f"\n> {tagline}")

    # Add each section only if non-empty
    for builder in [
        _section_vitals,
        _section_course,
        _section_terrain,
        _section_climate,
        _section_rating,
        _section_verdict,
        _section_logistics,
        _section_history,
        _section_non_negotiables,
        _section_riders_report,
        _section_tires,
        _section_citations,
    ]:
        section = builder(rd)
        if section:
            sections.append(f"\n{section}")

    sections.append(f"\n---\n*Generated by Gravel God on {now}. Source: {SITE_URL}/race/{slug}/*\n")

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate Markdown race profiles")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--slug", help="Generate a single race profile")
    args = parser.parse_args()

    if not INDEX_FILE.exists():
        print(f"ERROR: Race index not found: {INDEX_FILE}")
        return 1

    index = json.loads(INDEX_FILE.read_text())
    index_map = {r["slug"]: r for r in index}
    print(f"Loaded {len(index)} races from index")

    if args.slug:
        slugs = [args.slug]
    else:
        slugs = [r["slug"] for r in index]

    generated = 0
    skipped = 0
    total_bytes = 0

    for slug in slugs:
        entry = index_map.get(slug)
        if entry is None:
            print(f"  WARNING: {slug} not in index, skipping")
            skipped += 1
            continue

        md = generate_profile(slug, entry, RACE_DATA_DIR)
        if md is None:
            skipped += 1
            continue

        total_bytes += len(md)

        if not args.dry_run:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            out_file = OUTPUT_DIR / f"{slug}.md"
            out_file.write_text(md)

        generated += 1

    print(f"  Generated: {generated} profiles")
    print(f"  Skipped: {skipped}")
    print(f"  Total size: {total_bytes:,} bytes ({total_bytes / 1024:.0f} KB)")

    if args.dry_run:
        print(f"\n  [dry run] Would write to {OUTPUT_DIR}/")
    else:
        print(f"  Wrote to: {OUTPUT_DIR}/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
