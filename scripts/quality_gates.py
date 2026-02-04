#!/usr/bin/env python3
"""
Quality gates to catch AI slop before it hits production.

Run these checks on every output.
"""

import json
import re
from pathlib import Path


# ============================================
# SLOP PATTERNS - Phrases that indicate lazy AI output
# ============================================

# Multi-word phrases: matched as exact substrings (safe, low false-positive risk)
SLOP_PHRASES_MULTI = [
    # Generic filler
    "in conclusion",
    "it's worth noting",
    "it's important to note",
    "at the end of the day",
    "when it comes to",
    "in terms of",
    "the fact that",
    "needless to say",
    "it goes without saying",
    "as mentioned earlier",
    "as previously mentioned",
    "moving forward",
    "going forward",

    # AI enthusiasm
    "amazing opportunity",
    "incredible experience",
    "truly remarkable",
    "absolutely essential",
    "game-changer",
    "cutting-edge",
    "state-of-the-art",
    "best-in-class",
    "top-notch",
    "first-rate",

    # Hedge words (anti-Matti)
    "it seems like",
    "it appears that",
    "one might argue",
    "some would say",
    "maybe consider",
    "you might want to",
    "it could be said",

    # Generic encouragement (anti-Matti)
    "you've got this",
    "you can do it",
    "believe in yourself",
    "embrace the challenge",
    "find your inner",
    "unlock your potential",
    "on this journey",
    "your journey",

    # Filler transitions
    "without further ado",
    "let's dive in",
    "let's get started",
    "let's explore",
    "let's take a look",
    "let's break down",
    "here's the thing",
    "here's the deal",
    "the bottom line is",

    # Over-qualification
    "generally speaking",
    "for the most part",
    "in most cases",
    "more often than not",
    "by and large",

    # AI tell-tales (multi-word)
    "as an AI",
    "I don't have personal",
    "based on my training",
    "delve into",
]

# Single-word slop: matched with word boundaries (\bword\b) to prevent
# false positives like "vital" matching inside "vitals" or "robust" in
# "robust casing" (legitimate gravel context).
SLOP_WORDS_SINGLE = [
    "crucial",
    "vital",
    "essential",
    "comprehensive",
    "robust",
    "leverage",
    "utilize",
    "facilitate",
    "endeavor",
    "plethora",
    "arguably",
    "perhaps",
    "world-class",
]

# Domain allowlist: if these words appear near a slop word, suppress the flag.
# Key: slop word, Value: list of context words that make it legitimate.
DOMAIN_ALLOWLIST = {
    "robust": ["casing", "casings", "tire", "tires", "sidewall", "tubeless", "build"],
    "vital": ["statistics", "stats", "signs", "organs"],
    "essential": ["gear", "equipment", "kit", "tool", "supply", "rental", "car", "skill", "skills"],
    "comprehensive": ["coverage", "insurance"],
    "world-class": ["field", "athletes", "pros", "riders"],
    "perhaps": [],  # always flag
}


# Phrases that SHOULD appear (Matti voice indicators)
MATTI_INDICATORS = [
    # Direct address
    "you",
    "your",
    
    # Concrete language
    "mile",
    "hours",
    "percent",
    "%",
    "watts",
    "psi",
    
    # Honest/blunt markers
    "sucks",
    "hurts",
    "brutal",
    "honest",
    "reality",
    "truth",
    "actually",
    "really",
    
    # Specific not generic
    "specifically",
    "exactly",
]


def _extract_prose_from_json(content: str) -> str:
    """Extract only prose string values from JSON, skipping keys/IDs/URLs."""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return content  # Not JSON, return as-is

    prose_parts = []

    def walk(obj):
        if isinstance(obj, str):
            # Skip URLs, slugs, short labels
            if obj.startswith("http") or len(obj) < 15:
                return
            prose_parts.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(data)
    return " ".join(prose_parts)


def check_slop_phrases(content: str, content_type: str = None) -> dict:
    """Check for AI slop phrases.

    When content_type is 'json', only scans prose field values (not JSON keys
    or structural data) to prevent false positives on keys like 'vitals'.
    Uses word-boundary matching for single words to prevent substring matches
    (e.g., 'vital' inside 'vitals').
    """
    # For JSON content, extract only prose values
    if content_type == "json":
        scan_text = _extract_prose_from_json(content)
    else:
        scan_text = content

    scan_lower = scan_text.lower()
    found = []

    # Multi-word phrases: safe to substring match
    for phrase in SLOP_PHRASES_MULTI:
        if phrase.lower() in scan_lower:
            idx = scan_lower.find(phrase.lower())
            context = scan_text[max(0, idx - 30):idx + len(phrase) + 30]
            found.append({
                "phrase": phrase,
                "context": context.strip()
            })

    # Single words: use word boundary regex
    for word in SLOP_WORDS_SINGLE:
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        for match in pattern.finditer(scan_text):
            # Check domain allowlist — look for context words nearby
            start = max(0, match.start() - 60)
            end = min(len(scan_text), match.end() + 60)
            nearby = scan_text[start:end].lower()

            allowlist = DOMAIN_ALLOWLIST.get(word.lower(), [])
            if allowlist and any(ctx in nearby for ctx in allowlist):
                continue  # Legitimate use in gravel context

            context = scan_text[max(0, match.start() - 30):match.end() + 30]
            found.append({
                "phrase": word,
                "context": context.strip()
            })

    return {
        "passed": len(found) == 0,
        "slop_count": len(found),
        "slop_found": found
    }


def check_matti_voice(content: str) -> dict:
    """Check for Matti voice indicators."""
    content_lower = content.lower()
    
    found = [p for p in MATTI_INDICATORS if p.lower() in content_lower]
    missing = [p for p in MATTI_INDICATORS if p.lower() not in content_lower]
    
    # Calculate voice score
    score = len(found) / len(MATTI_INDICATORS) * 100
    
    return {
        "passed": score >= 40,  # At least 40% of indicators present
        "voice_score": round(score, 1),
        "indicators_found": found,
        "indicators_missing": missing[:5]  # First 5 missing
    }


def check_specificity(content: str) -> dict:
    """Check for specific details vs vague statements."""
    
    # Count specific markers
    numbers = len(re.findall(r'\b\d+\b', content))
    mile_markers = len(re.findall(r'mile\s*\d+', content.lower()))
    percentages = len(re.findall(r'\d+%', content))
    quotes = len(re.findall(r'["\'].*?["\']', content))
    urls = len(re.findall(r'https?://', content))
    usernames = len(re.findall(r'u/\w+', content))
    years = len(re.findall(r'\b20\d{2}\b', content))
    
    # Increased scoring for more sources
    specificity_score = (
        numbers * 1 +
        mile_markers * 5 +
        percentages * 3 +
        quotes * 4 +
        urls * 2 +  # URLs now worth 2x (more sources = better)
        usernames * 5 +
        years * 3
    )
    
    return {
        "passed": specificity_score >= 50,  # Increased threshold for more sources
        "specificity_score": specificity_score,
        "details": {
            "numbers": numbers,
            "mile_markers": mile_markers,
            "percentages": percentages,
            "quotes": quotes,
            "urls": urls,
            "reddit_usernames": usernames,
            "years_mentioned": years
        }
    }


def check_length_sanity(content: str, content_type: str) -> dict:
    """Check if content length is appropriate."""
    word_count = len(content.split())
    
    expected = {
        "research": (2000, 8000),    # Research dumps should be substantial (increased for more sources)
        "brief": (800, 2500),         # Briefs are condensed
        "json": (500, 3000),          # JSON varies
    }
    
    min_words, max_words = expected.get(content_type, (500, 5000))
    
    return {
        "passed": min_words <= word_count <= max_words,
        "word_count": word_count,
        "expected_range": f"{min_words}-{max_words}",
        "issue": "too_short" if word_count < min_words else ("too_long" if word_count > max_words else None)
    }


def check_required_sections(content: str, content_type: str) -> dict:
    """Check that required sections are present."""
    
    required = {
        "research": [
            "OFFICIAL DATA",
            "TERRAIN",
            "WEATHER",
            "REDDIT",
            "SUFFERING ZONE",
            "DNF",
            "EQUIPMENT",
            "LOGISTICS",
        ],
        "brief": [
            "RADAR SCORES",
            "Logistics",
            "Length", 
            "Technicality",
            "Elevation",
            "Climate",
            "Altitude",
            "Adventure",
            "PRESTIGE",
            "TRAINING",
            "BLACK PILL",
        ],
    }
    
    sections = required.get(content_type, [])
    content_upper = content.upper()
    
    found = [s for s in sections if s.upper() in content_upper]
    missing = [s for s in sections if s.upper() not in content_upper]
    
    return {
        "passed": len(missing) == 0,
        "sections_found": len(found),
        "sections_required": len(sections),
        "missing_sections": missing
    }


def check_source_citations(content: str) -> dict:
    """Check that claims have source URLs."""
    
    urls = re.findall(r'https?://[^\s\)\]\"\'<>]+', content)
    
    # Check for reddit, trainerroad, youtube sources
    reddit_sources = [u for u in urls if 'reddit.com' in u]
    tr_sources = [u for u in urls if 'trainerroad.com' in u]
    youtube_sources = [u for u in urls if 'youtube.com' in u or 'youtu.be' in u]
    official_sources = [u for u in urls if not any(x in u for x in ['reddit', 'youtube', 'trainerroad'])]
    
    return {
        "passed": len(urls) >= 15 and len(reddit_sources) >= 1,  # Updated: 15+ URLs required
        "total_urls": len(urls),
        "breakdown": {
            "reddit": len(reddit_sources),
            "trainerroad": len(tr_sources),
            "youtube": len(youtube_sources),
            "official/other": len(official_sources)
        }
    }


def check_source_diversity(content: str) -> dict:
    """Check that research includes diverse source types."""
    
    source_patterns = {
        "reddit": r'reddit\.com',
        "trainerroad": r'trainerroad\.com',
        "slowtwitch": r'slowtwitch\.com',
        "ridinggravel": r'ridinggravel\.com',
        "youtube": r'youtube\.com|youtu\.be',
        "velonews": r'velonews\.com',
        "cyclingtips": r'cyclingtips\.com',
        "escape_collective": r'escapecollective\.com',
        "team_blogs": r'rodeo-labs\.com|nofcks|sage\.bike|enve\.com',
        "official": r'gravel\.com|bikereg\.com|athlinks\.com|runsignup\.com',
    }
    
    found_sources = {}
    content_lower = content.lower()
    
    for name, pattern in source_patterns.items():
        matches = re.findall(pattern, content_lower)
        found_sources[name] = len(matches)
    
    # Count distinct source types
    source_types = sum(1 for count in found_sources.values() if count > 0)
    
    # Require at least 4 different source types
    return {
        "passed": source_types >= 4,
        "source_types_found": source_types,
        "source_breakdown": found_sources,
        "missing_categories": [k for k, v in found_sources.items() if v == 0]
    }


def run_all_quality_checks(content: str, content_type: str) -> dict:
    """Run all quality checks and return comprehensive report."""
    
    checks = {
        "slop": check_slop_phrases(content, content_type),
        "specificity": check_specificity(content),
        "length": check_length_sanity(content, content_type),
        "sections": check_required_sections(content, content_type),
    }
    
    # Voice check only for briefs (research dumps are raw data)
    if content_type == "brief":
        checks["voice"] = check_matti_voice(content)
    
    if content_type == "research":
        checks["citations"] = check_source_citations(content)
        checks["source_diversity"] = check_source_diversity(content)
    
    # Overall pass/fail
    all_passed = all(c["passed"] for c in checks.values())
    critical_failures = [name for name, check in checks.items() 
                        if not check["passed"] and name in ["slop", "sections", "citations", "source_diversity"]]
    
    return {
        "overall_passed": all_passed,
        "critical_failures": critical_failures,
        "checks": checks
    }


# ============================================
# CLI interface
# ============================================

if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="File to check")
    parser.add_argument("--type", required=True, choices=["research", "brief", "json"])
    parser.add_argument("--strict", action="store_true", help="Fail on any issue")
    args = parser.parse_args()
    
    content = Path(args.file).read_text()
    results = run_all_quality_checks(content, args.type)
    
    print("\n" + "="*60)
    print("QUALITY GATE RESULTS")
    print("="*60 + "\n")
    
    for name, check in results["checks"].items():
        status = "✓ PASS" if check["passed"] else "✗ FAIL"
        print(f"{status} | {name.upper()}")
        
        if not check["passed"]:
            # Print details for failures
            for key, val in check.items():
                if key != "passed" and val:
                    if isinstance(val, dict):
                        print(f"       {key}:")
                        for k, v in val.items():
                            print(f"         {k}: {v}")
                    elif isinstance(val, list) and len(val) > 0:
                        print(f"       {key}: {', '.join(str(v) for v in val[:5])}")
                    else:
                        print(f"       {key}: {val}")
        print()
    
    print("="*60)
    if results["overall_passed"]:
        print("✓ ALL QUALITY GATES PASSED")
    else:
        print(f"✗ FAILED: {', '.join(results['critical_failures'])}")
    print("="*60 + "\n")
    
    # Exit code
    if args.strict and not results["overall_passed"]:
        exit(1)
    elif results["critical_failures"]:
        exit(1)
    else:
        exit(0)

