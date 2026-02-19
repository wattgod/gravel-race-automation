#!/usr/bin/env python3
"""Extract rider quotes from community dumps and inject into explanations.

Parses community dumps for rider quotes, categorizes them by criterion,
then injects the best matching quote into explanations that lack quotes.

Usage:
    python scripts/extract_quotes.py              # Extract and inject
    python scripts/extract_quotes.py --dry-run    # Preview changes
    python scripts/extract_quotes.py --extract-only  # Just extract, save to data/quotes/
"""

import json
import pathlib
import re
import sys

RACE_DATA = pathlib.Path(__file__).parent.parent / "race-data"
RESEARCH_DIR = pathlib.Path(__file__).parent.parent / "research-dumps"
QUOTES_DIR = pathlib.Path(__file__).parent.parent / "data" / "quotes"

# Keywords that map quotes to criteria
CRITERION_KEYWORDS = {
    "technicality": [
        "technical", "singletrack", "rocky", "roots", "loose",
        "gravel", "sand", "mud", "washboard", "ruts", "hike-a-bike",
        "descen", "climb", "steep", "traction", "tire",
    ],
    "elevation": [
        "climb", "elevation", "ascent", "descen", "hill", "mountain",
        "gain", "gradient", "switchback", "vert", "steep",
    ],
    "altitude": [
        "altitude", "thin air", "oxygen", "elevation sick", "acclimate",
        "high altitude", "above sea level", "10,000", "11,000", "12,000",
    ],
    "climate": [
        "heat", "cold", "rain", "wind", "sun", "weather", "temperature",
        "humid", "dust", "mud", "storm", "snow", "ice", "freeze",
        "hot", "scorching", "sweat",
    ],
    "length": [
        "distance", "miles", "long", "endurance", "hours", "time",
        "fatigue", "bonk", "fuel", "nutrition", "water", "hydration",
    ],
    "expenses": [
        "cost", "price", "expensive", "cheap", "affordable", "budget",
        "hotel", "lodging", "travel", "fly", "drive", "registration",
        "entry fee", "dollar", "$",
    ],
    "logistics": [
        "park", "camp", "lodging", "hotel", "airport", "drive",
        "shuttle", "aid station", "support", "navigation", "mark",
        "sign", "course mark", "arrow",
    ],
    "field_depth": [
        "pro", "elite", "fast", "competitive", "field", "winner",
        "podium", "race", "sprint", "attack", "break", "pack",
        "watts", "power", "gap",
    ],
    "community": [
        "vibe", "community", "volunteer", "culture", "people",
        "friendly", "welcoming", "atmosphere", "spirit", "party",
        "beer", "barbecue", "celebrate", "cheer",
    ],
    "experience": [
        "experience", "beautiful", "scenic", "view", "landscape",
        "sunset", "sunrise", "wildlife", "adventure", "epic",
        "memory", "unforgettable", "bucket list",
    ],
    "adventure": [
        "adventure", "remote", "wild", "wilderness", "explore",
        "navigation", "self-supported", "bikepacking", "solo",
        "lost", "unknown", "uncharted",
    ],
    "race_quality": [
        "organized", "well-run", "professional", "smooth",
        "aid station", "support", "course", "timing", "results",
        "medal", "swag", "prize", "award",
    ],
    "prestige": [
        "championship", "world", "national", "qualify", "series",
        "legacy", "history", "iconic", "legendary", "reputation",
        "famous", "bucket list",
    ],
    "value": [
        "worth", "value", "return", "bang for", "recommend",
        "would do again", "come back", "every year", "must-do",
    ],
}


def extract_quotes_from_dump(text: str) -> list[dict]:
    """Extract rider quotes from a community dump."""
    quotes = []

    # Pattern 1: **Name [LEVEL]:** "quote" (source)
    # Also catches **Name [LEVEL] (Title):** "quote"
    pattern1 = re.compile(
        r'\*\*([A-Z][^*]+?)(?:\s*\[([A-Z]+)\])?\s*(?:\([^)]*\))?\s*:\*\*\s*'
        r'["\u201c]([^"\u201d]{20,}?)["\u201d]',
        re.MULTILINE
    )

    # Blocklist for non-rider "names" that appear in section headers
    blocklist = {
        "course composition", "course conditions", "surface variety",
        "terrain details", "rider experience", "local interactions",
        "gravel-induced problems", "pairs strategy", "suck mountain",
        "karst climate challenges", "route description", "race overview",
        "general consensus", "key takeaway", "course description",
        "race report", "event description",
    }

    for m in pattern1.finditer(text):
        name = m.group(1).strip()
        level = m.group(2) or ""
        quote = m.group(3).strip()

        # Skip non-rider attributions
        if name.lower() in blocklist:
            continue
        # Skip names that look like section headers (no capitals after first word, or >4 words)
        if len(name.split()) > 4:
            continue

        # Skip very long quotes (>300 chars) — trim them
        if len(quote) > 300:
            # Find last sentence boundary before 300
            cut = quote[:300].rfind(".")
            if cut > 100:
                quote = quote[:cut + 1]
            else:
                quote = quote[:300] + "..."
        quotes.append({
            "rider": name,
            "level": level,
            "quote": quote,
        })

    # Pattern 2: Section quotes like: "quote text" — attribution or (source)
    pattern2 = re.compile(
        r'(?:^|\n)\s*["\u201c]([^"\u201d]{30,300}?)["\u201d]\s*(?:—|--)\s*([A-Z][A-Za-z ]+)',
        re.MULTILINE
    )

    for m in pattern2.finditer(text):
        quote = m.group(1).strip()
        rider = m.group(2).strip()
        if rider and quote:
            quotes.append({
                "rider": rider,
                "level": "",
                "quote": quote,
            })

    return quotes


def categorize_quote(quote: str) -> list[str]:
    """Map a quote to relevant criteria based on keyword matching."""
    quote_lower = quote.lower()
    matches = []
    for criterion, keywords in CRITERION_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in quote_lower)
        if score >= 2:  # Need at least 2 keyword matches
            matches.append((criterion, score))
    # Sort by match strength
    matches.sort(key=lambda x: -x[1])
    return [c for c, _ in matches[:3]]  # Top 3 criteria


def has_quote(explanation: str) -> bool:
    """Check if explanation already contains a quoted phrase."""
    return bool(re.search(r'["\u201c\u201d][^"\u201c\u201d]{10,}["\u201c\u201d]', explanation))


def pick_best_quote(quotes: list[dict], criterion: str, explanation: str) -> dict | None:
    """Pick the best quote for a criterion that doesn't duplicate existing content."""
    # Filter to quotes categorized for this criterion
    candidates = []
    for q in quotes:
        criteria = categorize_quote(q["quote"])
        if criterion in criteria:
            candidates.append(q)

    if not candidates:
        return None

    # Prefer quotes from competitive/elite riders
    def score_quote(q):
        s = 0
        if q["level"] in ("ELITE", "COMPETITIVE"):
            s += 2
        # Prefer shorter, punchier quotes
        if len(q["quote"]) < 150:
            s += 1
        # Prefer quotes with specific details (numbers, place names)
        if re.search(r'\d+', q["quote"]):
            s += 1
        return s

    candidates.sort(key=lambda q: -score_quote(q))
    return candidates[0]


def main():
    dry_run = "--dry-run" in sys.argv
    extract_only = "--extract-only" in sys.argv

    QUOTES_DIR.mkdir(parents=True, exist_ok=True)

    races = sorted(RACE_DATA.glob("*.json"))
    total_extracted = 0
    total_injected = 0
    races_with_quotes = 0

    all_criteria = list(CRITERION_KEYWORDS.keys())

    for f in races:
        slug = f.stem

        # Load community dump
        dump_file = RESEARCH_DIR / f"{slug}-community.md"
        if not dump_file.exists():
            continue

        dump_text = dump_file.read_text()
        quotes = extract_quotes_from_dump(dump_text)

        if not quotes:
            continue

        races_with_quotes += 1
        total_extracted += len(quotes)

        # Save extracted quotes
        quote_file = QUOTES_DIR / f"{slug}.json"
        quote_data = []
        for q in quotes:
            criteria = categorize_quote(q["quote"])
            quote_data.append({**q, "criteria": criteria})
        quote_file.write_text(json.dumps(quote_data, indent=2, ensure_ascii=False) + "\n")

        if extract_only:
            continue

        # Load race data
        d = json.loads(f.read_text())
        race = d.get("race", d)
        bor = race.get("biased_opinion_ratings", {})
        modified = False

        for criterion in all_criteria:
            entry = bor.get(criterion, {})
            if not isinstance(entry, dict):
                continue
            explanation = entry.get("explanation", "")
            if not explanation:
                continue

            # Skip if already has a quote
            if has_quote(explanation):
                continue

            # Pick best quote for this criterion
            best = pick_best_quote(quotes, criterion, explanation)
            if not best:
                continue

            # Build injection: append quote at end
            rider = best["rider"]
            quote_text = best["quote"]
            # Trim quote if too long
            if len(quote_text) > 200:
                cut = quote_text[:200].rfind(".")
                if cut > 80:
                    quote_text = quote_text[:cut + 1]
                else:
                    quote_text = quote_text[:200] + "..."

            injection = f' As {rider} puts it: "{quote_text}"'

            new_explanation = explanation.rstrip() + injection

            # Don't exceed 800 chars (allowing more room since quotes add value)
            if len(new_explanation) > 800:
                continue

            if dry_run:
                print(f"  {slug}.{criterion}:")
                print(f"    QUOTE: {rider}: \"{quote_text[:100]}...\"")
                print()
                if total_injected > 20:
                    pass
            else:
                entry["explanation"] = new_explanation
                modified = True

            total_injected += 1

        if modified and not dry_run:
            f.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")

    print(f"\nExtracted {total_extracted} quotes from {races_with_quotes} races")
    if not extract_only:
        print(f"{'[DRY RUN] ' if dry_run else ''}Injected quotes into {total_injected} explanations")


if __name__ == "__main__":
    main()
