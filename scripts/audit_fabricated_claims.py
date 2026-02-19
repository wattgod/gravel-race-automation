#!/usr/bin/env python3
"""
Audit race JSON for claims not supported by research dumps.

Scans race profiles for high-confidence claim patterns (championship,
official, state, national, world) and cross-references against the
corresponding research dump files. Flags claims that appear in the
JSON but not in any research source.

This catches the specific failure mode where AI content fill (Claude API)
fabricates prestigious-sounding claims that have no basis in the research.

Usage:
    python scripts/audit_fabricated_claims.py                # all races
    python scripts/audit_fabricated_claims.py --slug NAME    # single race
    python scripts/audit_fabricated_claims.py --tier 1       # tier filter
    python scripts/audit_fabricated_claims.py --json         # JSON output
    python scripts/audit_fabricated_claims.py --strict       # exit 1 on warnings

Exit code: 0 = clean, 1 = unsupported claims found.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
RESEARCH_DIR = PROJECT_ROOT / "research-dumps"

# Patterns that indicate prestigious claims worth verifying.
# These are the exact patterns that led to fabricated content in
# Ned Gravel ("Colorado State Championship") and Pony Xpress (overstated).
CLAIM_PATTERNS = [
    # (pattern_for_json, research_verification_terms, claim_type)
    # research_verification_terms: list of terms — if ANY appear in research,
    # the claim is considered verified. Uses broader matching than the JSON
    # pattern to catch paraphrasing in research dumps.
    (r'\bstate\s+championship\b',
     ['state championship', 'state gravel championship', 'state championships'],
     'state championship'),
    (r'\bnational\s+championship\b',
     ['national championship', 'national championships', 'nationals'],
     'national championship'),
    (r'\bworld\s+championship\b',
     ['world championship', 'world championships', 'worlds'],
     'world championship'),
    (r'\bofficial\s+(?:state|national|world)\b',
     ['official', 'sanctioned', 'USAC', 'USA Cycling', 'UCI'],
     'official designation'),
    (r'\bUSA\s*Cycling\b',
     ['USA Cycling', 'USAC', 'USACycling'],
     'USA Cycling affiliation'),
    (r'\bUCI\b',
     ['UCI'],
     'UCI affiliation'),
    (r'\bstate\s+championship\s+(?:status|designation|event|course|race)\b',
     ['state championship', 'state gravel championship', 'state championships'],
     'state championship status'),
    (r'\bnational\s+(?:title|series|tour)\b',
     ['national', 'national series', 'national tour'],
     'national series'),
    (r'\blargest\s+(?:gravel|cycling|race)\b',
     ['largest'],
     'size claim'),
    (r'\boldest\s+(?:gravel|cycling|race)\b',
     ['oldest', 'first', 'inaugural', 'founded'],
     'age claim'),
]

# Fields to scan — these make direct claims about THIS race.
# Excludes: biased_opinion_ratings (well-cited from research),
# final_verdict.alternatives (references OTHER races),
# biased_opinion.summary/strengths/weaknesses/bottom_line
# (may reference other events for context — covered by verdict).
FIELDS_TO_SCAN = [
    'display_name', 'tagline',
    'vitals.terrain_types', 'vitals.prize_purse',
    'terrain.features',
    'gravel_god_rating.score_note',
    'biased_opinion.verdict',
    'final_verdict.one_liner', 'final_verdict.should_you_race',
    'history.origin_story', 'history.reputation',
    'guide_variables.race_challenges',
    'training_config.marketplace_variables.race_hook',
    'training_config.marketplace_variables.race_hook_detail',
    'training_config.marketplace_variables.non_negotiable_1',
    'training_config.marketplace_variables.non_negotiable_2',
    'training_config.marketplace_variables.non_negotiable_3',
]


def get_nested(data: dict, path: str):
    """Get a nested value from a dict using dot notation."""
    parts = path.split('.')
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def flatten_value(val) -> str:
    """Convert a value to a searchable string."""
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        return ' '.join(str(v) for v in val)
    if isinstance(val, dict):
        return ' '.join(str(v) for v in val.values())
    return str(val) if val is not None else ''


def load_research(slug: str) -> str:
    """Load all research dump content for a race slug.

    Tries multiple slug variations to handle naming mismatches between
    race JSON slugs and research dump filenames (e.g., gravel-grit-n-grind
    vs gravel-grit-grind).
    """
    # Generate slug variations to try
    slug_variants = [slug]
    # Try without common short words (n, and, the, of)
    for word in ['-n-', '-and-', '-the-', '-of-']:
        if word in slug:
            slug_variants.append(slug.replace(word, '-'))
    # Try with common short words removed entirely
    for word in ['-n-', '-and-']:
        if word in slug:
            slug_variants.append(slug.replace(word, ''))

    texts = []
    for f in RESEARCH_DIR.iterdir():
        if f.suffix != '.md':
            continue
        # Skip .bak files — these are often AI-generated and unreliable
        if '.bak' in f.name:
            continue
        # Check if filename matches any slug variant
        if any(f.name.startswith(variant) for variant in slug_variants):
            texts.append(f.read_text())
    return '\n'.join(texts)


def audit_race(race_path: Path) -> list[dict]:
    """Audit a single race JSON for unsupported claims.

    Returns list of findings, each with:
        slug, field, claim_type, text_found, in_research
    """
    data = json.loads(race_path.read_text())
    race = data.get('race', data)
    slug = race.get('slug', race_path.stem)

    research_text = load_research(slug)
    has_research = bool(research_text.strip())

    findings = []

    for field_path in FIELDS_TO_SCAN:
        val = get_nested(race, field_path)
        if val is None:
            continue

        text = flatten_value(val)
        if not text:
            continue

        for pattern, research_terms, claim_type in CLAIM_PATTERNS:
            # Skip UCI/USA Cycling checks on history fields — these often
            # describe founder credentials, not race designation claims
            if field_path.startswith('history.') and claim_type in (
                'UCI affiliation', 'USA Cycling affiliation'
            ):
                continue

            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            if not matches:
                continue

            # Check if this claim is backed by research using BROADER terms
            # (research dumps use different phrasing than generated JSON)
            if has_research:
                in_research = any(
                    term.lower() in research_text.lower()
                    for term in research_terms
                )
            else:
                # No research dump — flag everything as unverifiable
                in_research = False

            if not in_research:
                # Extract the surrounding context
                for m in matches:
                    start = max(0, m.start() - 30)
                    end = min(len(text), m.end() + 30)
                    context = text[start:end].strip()

                    findings.append({
                        'slug': slug,
                        'field': field_path,
                        'claim_type': claim_type,
                        'matched_text': m.group(0),
                        'context': context,
                        'has_research': has_research,
                    })

    return findings


def main():
    parser = argparse.ArgumentParser(
        description="Audit race JSON for fabricated claims")
    parser.add_argument('--slug', help='Audit a single race slug')
    parser.add_argument('--tier', type=int, help='Filter by tier (1-4)')
    parser.add_argument('--json', action='store_true', help='JSON output')
    parser.add_argument('--strict', action='store_true',
                        help='Exit 1 even on warnings')
    args = parser.parse_args()

    # Collect race files
    if args.slug:
        race_files = [RACE_DATA_DIR / f"{args.slug}.json"]
        if not race_files[0].exists():
            print(f"ERROR: {race_files[0]} not found")
            return 1
    else:
        race_files = sorted(RACE_DATA_DIR.glob("*.json"))

    # Optional tier filter
    if args.tier:
        filtered = []
        for rf in race_files:
            try:
                d = json.loads(rf.read_text())
                tier = d.get('race', d).get('gravel_god_rating', {}).get('tier')
                if tier == args.tier:
                    filtered.append(rf)
            except (json.JSONDecodeError, KeyError):
                pass
        race_files = filtered

    all_findings = []
    for rf in race_files:
        try:
            findings = audit_race(rf)
            all_findings.extend(findings)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  SKIP  {rf.name}: {e}", file=sys.stderr)

    if args.json:
        print(json.dumps(all_findings, indent=2))
    else:
        print("=" * 60)
        print("FABRICATED CLAIMS AUDIT")
        print("=" * 60)
        print(f"\nScanned {len(race_files)} race profiles")

        if not all_findings:
            print("\nNo unsupported claims found.")
        else:
            # Group by slug
            by_slug = {}
            for f in all_findings:
                by_slug.setdefault(f['slug'], []).append(f)

            print(f"\n{len(all_findings)} unsupported claim(s) in "
                  f"{len(by_slug)} race(s):\n")

            for slug, findings in sorted(by_slug.items()):
                print(f"  {slug}:")
                for f in findings:
                    research_note = ("NO RESEARCH DUMP"
                                     if not f['has_research']
                                     else "not in research")
                    print(f"    [{f['claim_type']}] {f['field']}")
                    print(f"      \"{f['context']}\"")
                    print(f"      ({research_note})")
                print()

    if all_findings:
        print(f"FAILED: {len(all_findings)} unsupported claim(s) found")
        return 1
    else:
        print("PASSED: All claims verified against research")
        return 0


if __name__ == "__main__":
    sys.exit(main())
