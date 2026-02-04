#!/usr/bin/env python3
"""
Adversarial LLM review — Stage 3.5 in the pipeline.

Sends race JSON to a cheap model (Haiku) acting as a hostile editor.
Catches issues that regex/mechanical checks can't:
- Logical contradictions between sections
- Context-dependent genericity
- Cross-section redundancy
- Unsupported claims
- Voice violations

Cost: ~3K tokens per race on Haiku = $0.009/race.

Usage:
    python adversarial_review.py --file race.json
    python adversarial_review.py --file race.json --fix  # Auto-generate fix prompt
    python adversarial_review.py --dir race-data/       # Batch mode
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("ERROR: pip install anthropic")
    sys.exit(2)


HOSTILE_EDITOR_PROMPT = """You are a hostile editor reviewing a gravel race profile for Gravel God Cycling.
Your job is to find problems. You are not helpful. You are critical.

Review this JSON and report ONLY problems:

1. SENTENCES: Any sentence over 30 words? Quote the full sentence.
2. SPECIFICITY: Any suffering zone without a real geographic name (trail, road, pass, landmark)? Flag it.
3. CLAIMS: Any statistic (%, number, "most", "largest", "first") without attribution? Flag it.
4. VOICE: Any sentence generic enough to appear on any race's website? Quote it.
5. LOGIC: Any contradiction between sections? (e.g., altitude score 1 but "significant altitude concern" in training)
6. COMPLETENESS: Any field that's "TBD", "coming soon", "data limited", or < 10 words when it should be substantial?
7. COPY-PASTE: Any phrase appearing in 2+ sections verbatim (exact or near-exact)?
8. SEVEN SWEEPS:
   - Clarity: jargon without explanation, unclear pronouns, overstuffed sentences?
   - So What: does every claim answer "why should I care as a racer?"
   - Prove It: is every assertion backed by a specific fact, number, or source?
   - Specificity: vague language that should be concrete numbers/names/places?

If no problems found: output exactly "CLEAN"
If problems found: list each with:
- The exact text that's problematic
- Which JSON field it's in (e.g., race.black_pill.reality)
- What's wrong and how to fix it

Be ruthless. Better to flag a false positive than miss real slop."""


def review_race_json(json_path: str, model: str = "claude-haiku-4-20250414") -> dict:
    """Send race JSON through adversarial LLM review."""
    data = json.loads(Path(json_path).read_text())

    # Extract just the race content (skip SEO metadata)
    race_content = json.dumps(data.get("race", data), indent=2)

    # Truncate if absurdly long (shouldn't happen with race profiles)
    if len(race_content) > 15000:
        race_content = race_content[:15000] + "\n... [truncated]"

    client = anthropic.Anthropic()

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": f"{HOSTILE_EDITOR_PROMPT}\n\n---\n\n{race_content}",
            }
        ],
    )

    review_text = response.content[0].text.strip()
    is_clean = review_text.upper().startswith("CLEAN")

    return {
        "file": str(json_path),
        "passed": is_clean,
        "review": review_text,
        "model": model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


def generate_fix_prompt(review_result: dict, json_path: str) -> str:
    """Generate a prompt to fix the issues found by the adversarial review."""
    if review_result["passed"]:
        return ""

    data = json.loads(Path(json_path).read_text())
    race_name = data.get("race", {}).get("name", Path(json_path).stem)

    return f"""Fix the following issues in the {race_name} race profile.
The adversarial review found these problems:

{review_result['review']}

Rules:
- Fix ONLY the flagged issues. Do not rewrite sections that weren't flagged.
- For run-on sentences: split into 2-3 shorter sentences, keep the same facts.
- For generic phrasing: replace with specific names, numbers, or places from the research.
- For unsupported claims: either add a source or soften the language (e.g., "reportedly" instead of stating as fact).
- For contradictions: check which section has the correct info and fix the other.
- For copy-paste: rewrite the duplicate in one section to say it differently.
- Maintain Matti's voice: direct, blunt, specific, no marketing speak.
- Output the complete corrected JSON.
"""


def batch_review(directory: str, model: str = "claude-haiku-4-20250414") -> List[dict]:
    """Review all JSON files in a directory."""
    results = []
    json_files = sorted(Path(directory).glob("*.json"))

    for json_file in json_files:
        print(f"Reviewing {json_file.name}...", end=" ", flush=True)
        try:
            result = review_race_json(str(json_file), model)
            status = "CLEAN" if result["passed"] else f"ISSUES ({result['output_tokens']} tokens)"
            print(status)
            results.append(result)
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "file": str(json_file),
                "passed": False,
                "review": f"ERROR: {e}",
                "model": model,
                "input_tokens": 0,
                "output_tokens": 0,
            })

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Adversarial LLM review for race JSON profiles (Stage 3.5)"
    )
    parser.add_argument("--file", help="Single JSON file to review")
    parser.add_argument("--dir", help="Directory of JSON files to batch review")
    parser.add_argument("--model", default="claude-haiku-4-20250414",
                        help="Model to use (default: claude-haiku-4-20250414)")
    parser.add_argument("--fix", action="store_true",
                        help="Generate fix prompt for issues found")
    parser.add_argument("--json-output", action="store_true",
                        help="Output raw JSON")
    args = parser.parse_args()

    if not args.file and not args.dir:
        parser.error("Provide --file or --dir")

    if args.file:
        result = review_race_json(args.file, args.model)

        if args.json_output:
            print(json.dumps(result, indent=2))
        else:
            print("\n" + "=" * 60)
            print("ADVERSARIAL REVIEW")
            print("=" * 60 + "\n")
            print(f"File: {result['file']}")
            print(f"Model: {result['model']}")
            print(f"Tokens: {result['input_tokens']} in / {result['output_tokens']} out")
            print()
            print(result["review"])
            print()
            print("=" * 60)
            if result["passed"]:
                print("✓ CLEAN — no issues found")
            else:
                print("✗ ISSUES FOUND — review above")
            print("=" * 60 + "\n")

        if args.fix and not result["passed"]:
            fix_prompt = generate_fix_prompt(result, args.file)
            print("\n--- FIX PROMPT ---\n")
            print(fix_prompt)

        sys.exit(0 if result["passed"] else 1)

    elif args.dir:
        results = batch_review(args.dir, args.model)

        if args.json_output:
            print(json.dumps(results, indent=2))
        else:
            print("\n" + "=" * 60)
            print("BATCH ADVERSARIAL REVIEW SUMMARY")
            print("=" * 60 + "\n")

            clean = [r for r in results if r["passed"]]
            flagged = [r for r in results if not r["passed"]]
            total_input = sum(r["input_tokens"] for r in results)
            total_output = sum(r["output_tokens"] for r in results)

            print(f"Total files:  {len(results)}")
            print(f"Clean:        {len(clean)}")
            print(f"Flagged:      {len(flagged)}")
            print(f"Total tokens: {total_input} in / {total_output} out")
            print()

            if flagged:
                print("FLAGGED FILES:")
                for r in flagged:
                    print(f"  ✗ {Path(r['file']).name}")
            print()

        sys.exit(0 if len(flagged) == 0 else 1)
