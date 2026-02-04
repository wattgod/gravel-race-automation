#!/usr/bin/env python3
"""
Research strength scorer — rates evidence quality for each race profile.

Produces a 0-100 score across 8 dimensions:
  1. Source diversity    — how many distinct source types cited
  2. Citation density    — URLs per 1K words in research dump
  3. Temporal depth      — how many distinct years referenced (longitudinal data)
  4. Specificity         — named geographic features vs generic labels
  5. Statistical backing — quantified claims (%, $, numbers with units)
  6. Voice authenticity  — real rider quotes with attribution
  7. Completeness        — required JSON sections populated with substance
  8. Cross-reference     — claims that appear in 2+ sources

Not customer-facing. Used internally to:
  - Prioritize which profiles need re-research
  - Flag thin profiles before they go live
  - Track overall DB quality over time

Usage:
    python research_strength.py --race unbound-200       # Score one race
    python research_strength.py --all                     # Score all races
    python research_strength.py --all --sort weakness     # Sort by weakest dimension
    python research_strength.py --all --csv               # Export to CSV
    python research_strength.py --all --embed             # Write scores into race JSON files
"""

import argparse
import csv
import json
import re
import sys
from io import StringIO
from pathlib import Path
from typing import Optional


RACE_DATA = Path(__file__).parent.parent / "race-data"
RESEARCH_DUMPS = Path(__file__).parent.parent / "research-dumps"
BRIEFS = Path(__file__).parent.parent / "briefs"

# Dimension weights (sum to 100)
WEIGHTS = {
    "source_diversity": 15,
    "citation_density": 10,
    "temporal_depth": 10,
    "specificity": 20,
    "statistical_backing": 15,
    "voice_authenticity": 10,
    "completeness": 15,
    "cross_reference": 5,
}

# Recognized source domains
SOURCE_DOMAINS = {
    "reddit": r"reddit\.com",
    "trainerroad": r"trainerroad\.com",
    "youtube": r"youtube\.com|youtu\.be",
    "velonews": r"velonews\.com",
    "cyclingtips": r"cyclingtips\.com",
    "escape_collective": r"escapecollective\.com",
    "slowtwitch": r"slowtwitch\.com",
    "ridinggravel": r"ridinggravel\.com",
    "strava": r"strava\.com",
    "ridewithgps": r"ridewithgps\.com",
    "official": r"bikereg\.com|athlinks\.com|runsignup\.com",
}

# Generic suffering zone patterns that indicate weak research
GENERIC_ZONE_NAMES = [
    r"(?i)^(the\s+)?(first|early|mid|late|final)\s+(push|grind|test|challenge|section|stretch|reality\s+check)",
    r"(?i)^(the\s+)?(opening|closing)\s+(wall|climb|stretch|push)",
    r"(?i)^(dark\s+thoughts|meltdown|salvation|breaking\s+point)",
    r"(?i)^(checkpoint|aid\s+station)\s+(salvation|relief)",
]

# Required JSON sections for completeness scoring
REQUIRED_SECTIONS = {
    "race.tagline": lambda r: len(r.get("tagline", "")) > 15,
    "race.vitals.distance_mi": lambda r: r.get("vitals", {}).get("distance_mi") is not None,
    "race.vitals.elevation_ft": lambda r: r.get("vitals", {}).get("elevation_ft") is not None,
    "race.vitals.location": lambda r: len(r.get("vitals", {}).get("location", "")) > 3,
    "race.vitals.date": lambda r: len(r.get("vitals", {}).get("date", "")) > 3,
    "race.vitals.registration": lambda r: len(r.get("vitals", {}).get("registration", "")) > 10,
    "race.vitals.aid_stations": lambda r: len(r.get("vitals", {}).get("aid_stations", "")) > 10,
    "race.climate.description": lambda r: len(r.get("climate", {}).get("description", "")) > 30,
    "race.terrain.surface": lambda r: len(r.get("terrain", {}).get("surface", "")) > 20,
    "race.gravel_god_rating.overall_score": lambda r: r.get("gravel_god_rating", {}).get("overall_score") is not None,
    "race.course_description.character": lambda r: len(r.get("course_description", {}).get("character", "")) > 50,
    "race.course_description.suffering_zones": lambda r: len(r.get("course_description", {}).get("suffering_zones", [])) >= 2,
    "race.biased_opinion.summary": lambda r: len(r.get("biased_opinion", {}).get("summary", "")) > 50,
    "race.black_pill": lambda r: len(str(r.get("black_pill", {}).get("reality", r.get("black_pill", {}).get("truth", "")))) > 50,
    "race.logistics": lambda r: len(str(r.get("logistics", {}))) > 50,
    "race.history.origin_story": lambda r: len(r.get("history", {}).get("origin_story", "")) > 20,
    "race.history.notable_moments": lambda r: len(r.get("history", {}).get("notable_moments", [])) >= 2,
}


def _score_source_diversity(content: str) -> tuple:
    """Score: how many distinct source types are cited. 0-100."""
    found = set()
    content_lower = content.lower()
    for name, pattern in SOURCE_DOMAINS.items():
        if re.search(pattern, content_lower):
            found.add(name)

    # Also check for official race website
    urls = re.findall(r'https?://[^\s\"\]\)]+', content)
    unique_domains = set()
    for url in urls:
        match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        if match:
            unique_domains.add(match.group(1))

    total_types = max(len(found), len(unique_domains))

    # 7+ source types = 100, 5-6 = 80, 3-4 = 60, 1-2 = 30, 0 = 0
    if total_types >= 7:
        score = 100
    elif total_types >= 5:
        score = 80
    elif total_types >= 3:
        score = 60
    elif total_types >= 1:
        score = 30
    else:
        score = 0

    return score, {
        "source_types_found": total_types,
        "recognized_sources": sorted(found),
        "unique_domains": len(unique_domains),
    }


def _score_citation_density(content: str) -> tuple:
    """Score: URLs per 1K words. 0-100."""
    urls = re.findall(r'https?://[^\s\"\]\)]+', content)
    word_count = len(content.split())
    if word_count == 0:
        return 0, {"urls": 0, "words": 0, "per_1k": 0}

    per_1k = (len(urls) / word_count) * 1000

    # 10+ per 1K = 100, 5-9 = 80, 2-4 = 50, 1 = 20, 0 = 0
    if per_1k >= 10:
        score = 100
    elif per_1k >= 5:
        score = 80
    elif per_1k >= 2:
        score = 50
    elif per_1k >= 0.5:
        score = 20
    else:
        score = 5  # Small baseline for profiles without research dumps

    return score, {"urls": len(urls), "words": word_count, "per_1k": round(per_1k, 2)}


def _score_temporal_depth(content: str) -> tuple:
    """Score: distinct years referenced. 0-100."""
    years = set(re.findall(r'\b(20[0-2]\d)\b', content))

    if len(years) >= 5:
        score = 100
    elif len(years) >= 3:
        score = 75
    elif len(years) >= 2:
        score = 50
    elif len(years) >= 1:
        score = 25
    else:
        score = 0

    return score, {"years_found": sorted(years), "count": len(years)}


def _score_specificity(race: dict) -> tuple:
    """Score: real geographic names vs generic labels. 0-100."""
    zones = race.get("course_description", {}).get("suffering_zones", [])
    features = race.get("terrain", {}).get("features", [])
    history_moments = race.get("history", {}).get("notable_moments", [])

    total_named = 0
    total_generic = 0
    generic_examples = []

    for zone in zones:
        label = zone.get("label", "")
        is_generic = any(re.search(p, label) for p in GENERIC_ZONE_NAMES)
        if is_generic:
            total_generic += 1
            generic_examples.append(label)
        elif label:
            total_named += 1

    # Named terrain features count positively
    total_named += len(features)

    # Named people/events in history count positively
    for moment in history_moments:
        if re.search(r'[A-Z][a-z]+ [A-Z]', str(moment)):
            total_named += 1

    total = total_named + total_generic
    if total == 0:
        return 0, {"named": 0, "generic": 0, "generic_examples": []}

    ratio = total_named / total
    score = int(ratio * 100)

    # Bonus: lots of named features even if some generic exist
    if total_named >= 6:
        score = min(100, score + 15)

    return score, {
        "named": total_named,
        "generic": total_generic,
        "generic_examples": generic_examples,
        "ratio": round(ratio, 2),
    }


def _score_statistical_backing(content: str) -> tuple:
    """Score: quantified claims. 0-100."""
    percentages = re.findall(r'\d+%', content)
    dollar_amounts = re.findall(r'\$\d+', content)
    temps = re.findall(r'\d+°[FCf]|\d+\s*degrees', content)
    distances = re.findall(r'\d+\s*(?:mi(?:les?)?|km|ft|feet|meters?)\b', content, re.I)
    time_refs = re.findall(r'\d+\s*(?:hours?|hrs?|minutes?|min)\b', content, re.I)
    rider_counts = re.findall(r'\d{3,}\s*(?:riders?|participants?|entries|finishers?|starters?)\b', content, re.I)
    dnf_data = re.findall(r'\d+%?\s*(?:DNF|abandon|dropout|scratched)\b', content, re.I)

    total = (len(percentages) + len(dollar_amounts) + len(temps) +
             len(distances) + len(time_refs) + len(rider_counts) + len(dnf_data))

    if total >= 25:
        score = 100
    elif total >= 15:
        score = 80
    elif total >= 8:
        score = 60
    elif total >= 3:
        score = 35
    else:
        score = 10

    return score, {
        "total": total,
        "percentages": len(percentages),
        "dollar_amounts": len(dollar_amounts),
        "temperatures": len(temps),
        "distances": len(distances),
        "time_refs": len(time_refs),
        "rider_counts": len(rider_counts),
        "dnf_data": len(dnf_data),
    }


def _score_voice_authenticity(content: str) -> tuple:
    """Score: real rider quotes with attribution. 0-100."""
    reddit_users = re.findall(r'u/\w+', content)
    quoted_text = re.findall(r'["\u2018\u2019\u201c\u201d]([^"\u2018\u2019\u201c\u201d]{15,})["\u2018\u2019\u201c\u201d]', content)
    # Single quotes used as apostrophes in contractions are common, look for longer quoted phrases
    single_quoted = re.findall(r"'([^']{25,})'", content)
    forum_attributions = re.findall(r'(?:said|posted|wrote|reported|mentioned)\s+(?:by|on|in)\b', content, re.I)

    total_quotes = len(quoted_text) + len(single_quoted)
    total_attributions = len(reddit_users) + len(forum_attributions)

    # Best: quotes WITH attribution
    if total_quotes >= 3 and total_attributions >= 2:
        score = 100
    elif total_quotes >= 3 or total_attributions >= 2:
        score = 70
    elif total_quotes >= 1 or total_attributions >= 1:
        score = 40
    elif total_quotes > 0:
        score = 20
    else:
        score = 5

    return score, {
        "quoted_passages": total_quotes,
        "reddit_users": len(reddit_users),
        "forum_attributions": len(forum_attributions),
    }


def _score_completeness(race: dict) -> tuple:
    """Score: required sections populated with substance. 0-100."""
    passed = 0
    failed = []

    for section, check_fn in REQUIRED_SECTIONS.items():
        try:
            if check_fn(race):
                passed += 1
            else:
                failed.append(section)
        except (TypeError, AttributeError):
            failed.append(section)

    total = len(REQUIRED_SECTIONS)
    score = int((passed / total) * 100) if total > 0 else 0

    return score, {
        "passed": passed,
        "total": total,
        "missing": failed,
    }


def _score_cross_reference(content: str, race: dict) -> tuple:
    """Score: claims that appear corroborated. 0-100.

    Heuristic: if a specific number/stat appears in multiple sections
    of the JSON, it's likely been cross-referenced.
    """
    # Extract all numbers with context from different top-level sections
    sections_with_stats = {}
    for key in ("tagline", "climate", "terrain", "course_description",
                "biased_opinion", "black_pill", "logistics", "history"):
        section_text = json.dumps(race.get(key, ""))
        stats = set(re.findall(r'\b\d{2,}\b', section_text))
        if stats:
            sections_with_stats[key] = stats

    # Count numbers that appear in 2+ sections
    all_stats = {}
    for section, stats in sections_with_stats.items():
        for s in stats:
            all_stats.setdefault(s, []).append(section)

    cross_referenced = {s: sections for s, sections in all_stats.items() if len(sections) >= 2}

    if len(cross_referenced) >= 5:
        score = 100
    elif len(cross_referenced) >= 3:
        score = 75
    elif len(cross_referenced) >= 1:
        score = 50
    else:
        score = 15  # Baseline — JSON was at least internally structured

    return score, {
        "cross_referenced_stats": len(cross_referenced),
        "examples": {k: v for k, v in list(cross_referenced.items())[:5]},
    }


def score_race(slug: str) -> dict:
    """Score research strength for a single race."""
    json_path = RACE_DATA / f"{slug}.json"
    research_path = RESEARCH_DUMPS / f"{slug}-raw.md"
    brief_path = BRIEFS / f"{slug}-brief.md"

    if not json_path.exists():
        return {"slug": slug, "error": "no JSON profile found", "overall": 0}

    data = json.loads(json_path.read_text())
    race = data.get("race", {})

    # Combine all available text for citation analysis
    all_content = json_path.read_text()
    has_research = research_path.exists()
    has_brief = brief_path.exists()

    if has_research:
        all_content += "\n" + research_path.read_text()
    if has_brief:
        all_content += "\n" + brief_path.read_text()

    # Score each dimension
    dimensions = {}

    score, detail = _score_source_diversity(all_content)
    dimensions["source_diversity"] = {"score": score, **detail}

    score, detail = _score_citation_density(all_content)
    dimensions["citation_density"] = {"score": score, **detail}

    score, detail = _score_temporal_depth(all_content)
    dimensions["temporal_depth"] = {"score": score, **detail}

    score, detail = _score_specificity(race)
    dimensions["specificity"] = {"score": score, **detail}

    score, detail = _score_statistical_backing(all_content)
    dimensions["statistical_backing"] = {"score": score, **detail}

    score, detail = _score_voice_authenticity(all_content)
    dimensions["voice_authenticity"] = {"score": score, **detail}

    score, detail = _score_completeness(race)
    dimensions["completeness"] = {"score": score, **detail}

    score, detail = _score_cross_reference(all_content, race)
    dimensions["cross_reference"] = {"score": score, **detail}

    # Weighted overall
    overall = sum(
        dimensions[dim]["score"] * (WEIGHTS[dim] / 100)
        for dim in WEIGHTS
    )

    # Determine grade
    if overall >= 80:
        grade = "A"
    elif overall >= 65:
        grade = "B"
    elif overall >= 45:
        grade = "C"
    elif overall >= 25:
        grade = "D"
    else:
        grade = "F"

    # Identify weakest dimension
    weakest = min(dimensions, key=lambda d: dimensions[d]["score"])

    return {
        "slug": slug,
        "overall": round(overall, 1),
        "grade": grade,
        "has_research_dump": has_research,
        "has_brief": has_brief,
        "weakest_dimension": weakest,
        "weakest_score": dimensions[weakest]["score"],
        "dimensions": dimensions,
    }


def embed_scores(slug: str, scores: dict):
    """Write research_strength into the race JSON's research_metadata."""
    json_path = RACE_DATA / f"{slug}.json"
    data = json.loads(json_path.read_text())

    race = data.get("race", {})
    meta = race.setdefault("research_metadata", {})

    meta["research_strength"] = {
        "overall": scores["overall"],
        "grade": scores["grade"],
        "weakest": scores["weakest_dimension"],
        "has_research_dump": scores["has_research_dump"],
        "dimensions": {
            dim: scores["dimensions"][dim]["score"]
            for dim in WEIGHTS
        },
        "scored_at": "2026-02-04",
    }

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Score research strength for race profiles")
    parser.add_argument("--race", help="Score a single race")
    parser.add_argument("--all", action="store_true", help="Score all races")
    parser.add_argument("--sort", choices=["overall", "weakness", "grade", "name"],
                        default="overall", help="Sort order (default: overall descending)")
    parser.add_argument("--csv", action="store_true", help="Output CSV")
    parser.add_argument("--json-output", action="store_true", help="Output JSON")
    parser.add_argument("--embed", action="store_true",
                        help="Write scores into race JSON research_metadata")
    parser.add_argument("--min-grade", choices=["A", "B", "C", "D", "F"],
                        help="Only show races at or below this grade")
    args = parser.parse_args()

    if not args.race and not args.all:
        parser.error("Provide --race <slug> or --all")

    if args.race:
        result = score_race(args.race)
        if args.embed:
            embed_scores(args.race, result)
            print(f"Embedded scores into race-data/{args.race}.json")

        if args.json_output:
            print(json.dumps(result, indent=2))
        else:
            _print_detail(result)
    else:
        slugs = sorted(f.stem for f in RACE_DATA.glob("*.json"))
        results = [score_race(slug) for slug in slugs]

        if args.embed:
            for r in results:
                if "error" not in r:
                    embed_scores(r["slug"], r)
            print(f"Embedded scores into {len(results)} race JSON files\n")

        # Filter by grade
        if args.min_grade:
            grade_order = {"A": 0, "B": 1, "C": 2, "D": 3, "F": 4}
            threshold = grade_order[args.min_grade]
            results = [r for r in results if grade_order.get(r.get("grade", "F"), 4) >= threshold]

        # Sort
        if args.sort == "overall":
            results.sort(key=lambda r: r.get("overall", 0), reverse=True)
        elif args.sort == "weakness":
            results.sort(key=lambda r: r.get("weakest_score", 0))
        elif args.sort == "grade":
            grade_order = {"A": 0, "B": 1, "C": 2, "D": 3, "F": 4}
            results.sort(key=lambda r: (grade_order.get(r.get("grade", "F"), 4), -r.get("overall", 0)))
        elif args.sort == "name":
            results.sort(key=lambda r: r["slug"])

        if args.json_output:
            print(json.dumps(results, indent=2))
        elif args.csv:
            _print_csv(results)
        else:
            _print_table(results)


def _print_detail(result: dict):
    """Print detailed score for one race."""
    print(f"\n{'=' * 60}")
    print(f"RESEARCH STRENGTH: {result['slug']}")
    print(f"{'=' * 60}\n")
    print(f"Overall: {result['overall']}/100 (Grade {result['grade']})")
    print(f"Research dump: {'Yes' if result.get('has_research_dump') else 'No'}")
    print(f"Brief: {'Yes' if result.get('has_brief') else 'No'}")
    print(f"Weakest: {result['weakest_dimension']} ({result['weakest_score']}/100)")
    print()

    for dim, data in result["dimensions"].items():
        bar_len = data["score"] // 5
        bar = "█" * bar_len + "░" * (20 - bar_len)
        weight = WEIGHTS[dim]
        print(f"  {dim:<22} {bar} {data['score']:>3}/100 (weight: {weight}%)")

        # Print key details
        for k, v in data.items():
            if k == "score":
                continue
            if isinstance(v, list) and len(v) > 0:
                print(f"    {k}: {', '.join(str(x) for x in v[:5])}")
            elif isinstance(v, dict):
                continue  # Skip nested dicts in detail view
            elif v and v != 0:
                print(f"    {k}: {v}")
    print()


def _print_table(results: list):
    """Print summary table."""
    print(f"\n{'=' * 100}")
    print(f"RESEARCH STRENGTH — ALL RACES")
    print(f"{'=' * 100}\n")

    header = f"{'Race':<30} {'Grade':>5} {'Score':>5}  {'Src':>3} {'Cit':>3} {'Tmp':>3} {'Spc':>3} {'Sta':>3} {'Vox':>3} {'Cmp':>3} {'Xrf':>3}  {'Weakest':<20}"
    print(header)
    print("-" * len(header))

    for r in results:
        if "error" in r:
            print(f"  {r['slug']:<30} ERROR: {r['error']}")
            continue

        dims = r["dimensions"]
        print(f"  {r['slug']:<28} {r['grade']:>5} {r['overall']:>5.0f}  "
              f"{dims['source_diversity']['score']:>3} "
              f"{dims['citation_density']['score']:>3} "
              f"{dims['temporal_depth']['score']:>3} "
              f"{dims['specificity']['score']:>3} "
              f"{dims['statistical_backing']['score']:>3} "
              f"{dims['voice_authenticity']['score']:>3} "
              f"{dims['completeness']['score']:>3} "
              f"{dims['cross_reference']['score']:>3}  "
              f"{r['weakest_dimension']}")

    # Summary
    grades = {}
    for r in results:
        g = r.get("grade", "?")
        grades[g] = grades.get(g, 0) + 1

    print(f"\n{'=' * 100}")
    print(f"Total: {len(results)} races | " +
          " | ".join(f"Grade {g}: {c}" for g, c in sorted(grades.items())))
    avg = sum(r.get("overall", 0) for r in results) / max(len(results), 1)
    print(f"Average score: {avg:.1f}/100")
    print(f"{'=' * 100}\n")


def _print_csv(results: list):
    """Print CSV output."""
    output = StringIO()
    writer = csv.writer(output)
    dims = list(WEIGHTS.keys())
    writer.writerow(["slug", "overall", "grade", "has_research", "has_brief", "weakest"] + dims)
    for r in results:
        if "error" in r:
            continue
        row = [r["slug"], r["overall"], r["grade"],
               r.get("has_research_dump", False), r.get("has_brief", False),
               r["weakest_dimension"]]
        row += [r["dimensions"][d]["score"] for d in dims]
        writer.writerow(row)
    print(output.getvalue())


if __name__ == "__main__":
    main()
