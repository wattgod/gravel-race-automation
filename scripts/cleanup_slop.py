#!/usr/bin/env python3
"""
Targeted slop phrase cleanup across all race profile explanations.

Does mechanical text replacements to remove slop words without
changing meaning. Validates each fix passes quality gates before saving.

Usage:
    python scripts/cleanup_slop.py              # Fix all
    python scripts/cleanup_slop.py --dry-run    # Preview without writing
"""

import argparse
import json
import re
import sys
from pathlib import Path

RACE_DATA = Path(__file__).parent.parent / "race-data"
COMPONENTS = [
    'logistics', 'length', 'technicality', 'elevation', 'climate',
    'altitude', 'adventure', 'prestige', 'race_quality', 'experience',
    'community', 'field_depth', 'value', 'expenses'
]

sys.path.insert(0, str(Path(__file__).parent))
from quality_gates import check_slop_phrases


def clean_explanation(text):
    """Apply mechanical slop removals. Returns cleaned text."""
    original = text

    # "legitimate " / "Legitimate " — just delete (keeps the noun)
    text = re.sub(r'\blegitimate\s+', '', text, flags=re.IGNORECASE)

    # "legitimately " — just delete
    text = re.sub(r'\blegitimately\s+', '', text, flags=re.IGNORECASE)

    # "genuine " — just delete
    text = re.sub(r'\bgenuine\s+', '', text, flags=re.IGNORECASE)

    # "genuinely " — just delete
    text = re.sub(r'\bgenuinely\s+', '', text, flags=re.IGNORECASE)

    # "isn't exactly " → "isn't "
    text = re.sub(r"isn't exactly\s+", "isn't ", text, flags=re.IGNORECASE)

    # "not exactly " → "not "
    text = re.sub(r'\bnot exactly\s+', 'not ', text, flags=re.IGNORECASE)

    # "the fact that " — delete (handle sentence-start capitalization)
    text = re.sub(r'\.\s+The fact that\s+', '. ', text)
    text = re.sub(r'^The fact that\s+', '', text)
    text = re.sub(r'\bthe fact that\s+', '', text, flags=re.IGNORECASE)

    # "world-class" → "elite" (or "top-tier" for non-person contexts)
    text = re.sub(r'\bworld-class\s+(?=talent|field|competition|riders|athletes)',
                  'elite ', text, flags=re.IGNORECASE)
    text = re.sub(r'\bworld-class\s+(?=event|production|organization|operations)',
                  'top-tier ', text, flags=re.IGNORECASE)
    text = re.sub(r'\bWorld-class\s+', 'Outstanding ', text)
    text = re.sub(r'\bworld-class\s+', 'outstanding ', text, flags=re.IGNORECASE)

    # "arguably " — delete
    text = re.sub(r'\barguably\s+', '', text, flags=re.IGNORECASE)

    # "perhaps " — delete
    text = re.sub(r'\bperhaps\s+', '', text, flags=re.IGNORECASE)

    # "crucial " → "key "
    text = re.sub(r'\bcrucial\s+', 'key ', text, flags=re.IGNORECASE)

    # "comprehensive " → "full "
    text = re.sub(r'\bcomprehensive\s+', 'full ', text, flags=re.IGNORECASE)

    # "leverage " (as verb) → "use "
    text = re.sub(r'\bleverage\s+(?=it|the|this|that)', 'use ', text, flags=re.IGNORECASE)

    # "essential" in non-poetic context → "necessary"
    # Skip "the essential" (poetic: "stripped of everything but the essential hurt")
    text = re.sub(r'\bis essential\b', 'is necessary', text, flags=re.IGNORECASE)

    # "bigger problems than" — rewrite the snark
    text = re.sub(r"you've got bigger problems than race selection",
                  "altitude won't be the deciding factor", text, flags=re.IGNORECASE)

    # Fix double spaces from deletions
    text = re.sub(r'  +', ' ', text)

    # Fix orphaned sentence-start lowercase after deletion
    # e.g. "... mecca. racing here" → "... mecca. Racing here"
    def fix_sentence_start(m):
        return m.group(1) + m.group(2).upper()
    text = re.sub(r'(\.\s+)([a-z])', fix_sentence_start, text)

    # Fix explanation starting with lowercase (e.g. "genuine X" → "X" after deletion)
    text = text.strip()
    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    return text


def main():
    parser = argparse.ArgumentParser(description="Clean slop phrases from explanations")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    total_fixed = 0
    total_remaining = 0
    files_changed = 0

    for path in sorted(RACE_DATA.glob("*.json")):
        data = json.loads(path.read_text())
        race = data.get("race", data)
        bor = race.get("biased_opinion_ratings", {})
        file_changed = False

        for k in COMPONENTS:
            entry = bor.get(k)
            if not isinstance(entry, dict):
                continue
            exp = entry.get("explanation", "")
            if not exp:
                continue

            result = check_slop_phrases(exp)
            if result["passed"]:
                continue

            cleaned = clean_explanation(exp)
            if cleaned == exp:
                # Couldn't fix — report
                phrases = [s["phrase"] for s in result["slop_found"]]
                total_remaining += len(phrases)
                continue

            # Verify fix actually passes
            recheck = check_slop_phrases(cleaned)
            if recheck["passed"]:
                if args.dry_run:
                    print(f"  {path.stem}.{k}: WOULD FIX")
                    old_phrases = [s["phrase"] for s in result["slop_found"]]
                    print(f"    removed: {old_phrases}")
                entry["explanation"] = cleaned
                file_changed = True
                total_fixed += len(result["slop_found"])
            else:
                # Partial fix — still has slop
                remaining = [s["phrase"] for s in recheck["slop_found"]]
                fixed_count = len(result["slop_found"]) - len(remaining)
                if fixed_count > 0:
                    entry["explanation"] = cleaned
                    file_changed = True
                    total_fixed += fixed_count
                total_remaining += len(remaining)
                if args.dry_run:
                    print(f"  {path.stem}.{k}: PARTIAL — remaining: {remaining}")

        if file_changed and not args.dry_run:
            if "race" in data:
                data["race"] = race
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            files_changed += 1

    prefix = "DRY RUN — " if args.dry_run else ""
    print(f"\n{prefix}{total_fixed} slop phrases fixed, {total_remaining} remaining, {files_changed} files updated")


if __name__ == "__main__":
    main()
